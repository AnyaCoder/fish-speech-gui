import asyncio
import io
import os
import re
import subprocess
import time
import wave
from pathlib import Path
from typing import AsyncIterator, Iterator, List

import numpy as np
import ormsgpack
import psutil
import pyaudio
import requests
import sounddevice as sd
from PyQt6.QtCore import QMutex, QMutexLocker, QObject, QRunnable, QThread, pyqtSignal

from fish.config import config
from fish.services.tts import ServeReferenceAudio, ServeTTSRequest
from fish.utils.i18n import _t

from .network import WebSocketClient

if os.environ.get("LOGURU", 0) == 0:
    from fish.modules.log import logger

    logger.warning("set LOGURU=1 to enable real console log.")
else:
    from loguru import logger


env = os.environ.copy()
env["MODELSCOPE_CACHE"] = os.path.join(os.environ.get("TEMP", "."), "funasr")


class BaseWorker(QThread):
    finished_signal = pyqtSignal(str)
    output_signal = pyqtSignal(str, bool, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.mutex = QMutex()
        self.is_running = False
        self.is_interrupted = False

    def emit_output(self, opt: str):
        is_progress, percentage = self.extract_percentage(opt)
        self.output_signal.emit(opt, is_progress, percentage)

    def extract_percentage(self, opt: str):
        match = re.search(r"(\d{1,3})%\|", opt)  # '100%|'
        if match:
            return True, match.group(1)
        return False, "0"


class AsyncTaskWorker(QObject):
    finish_signal = pyqtSignal()

    def __init__(self, loop: asyncio.AbstractEventLoop):
        super().__init__()
        self.loop = loop
        self._task = None
        self.cancel_event = asyncio.Event()

    def run(self):
        self._task = self.loop.create_task(self._execute_task())
        self._task.add_done_callback(self._on_task_done)
        try:
            self.loop.run_until_complete(self._task)
        except asyncio.CancelledError:
            pass  # Don't show redundant error

    async def _execute_task(self):
        raise NotImplementedError("Subclasses should implement this method")

    def cancel(self):
        if self._task:
            self.cancel_event.set()
            self._task.cancel()
            self._task = None

    def _on_task_done(self, task: asyncio.Task):
        self.finish_signal.emit()
        if task.cancelled():
            logger.warning("Task was cancelled")
        elif task.exception():
            logger.error(f"Task encountered an exception: {task.exception()}")
        else:
            logger.info("Task completed successfully")


class AsyncTaskRunner(QRunnable):
    def __init__(self, worker: AsyncTaskWorker):
        super().__init__()
        self.worker = worker

    def run(self):
        self.worker.run()

    def cancel(self):
        self.worker.cancel()


class SubprocessWorker(BaseWorker):
    def __init__(self, command, parent=None):
        super().__init__(parent)
        self.command = command
        self.process = None

    def run(self):
        with QMutexLocker(self.mutex):
            self.is_running = True

        try:
            self.process = subprocess.Popen(
                self.command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                errors="replace",
                universal_newlines=True,
                env=env,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            while self.is_running:
                opt = self.process.stdout.readline()
                if opt == "" and self.process.poll() is not None:
                    break
                if opt:
                    self.emit_output(opt.strip())

            exit_code = self.process.wait()
            with QMutexLocker(self.mutex):
                if not self.is_interrupted:
                    self.finished_signal.emit(
                        _t("worker.f_signal.complete").format(
                            cmd=" ".join(self.command), exit_code=exit_code
                        )
                    )
        except Exception as e:
            self.finished_signal.emit(_t("worker.f_signal.error").format(e=str(e)))
            self.stop()

    def stop(self):
        with QMutexLocker(self.mutex):
            if not self.is_running:
                return
            self.is_running = False
            self.is_interrupted = True
        self.terminate_process()
        self.finished_signal.emit(_t("worker.f_signal.stop"))

    def terminate_process(self):
        if self.process:
            try:
                parent = psutil.Process(self.process.pid)
                children = parent.children(recursive=True)
                for child in children:
                    child.terminate()
                parent.terminate()

                gone, still_alive = psutil.wait_procs(children + [parent], timeout=5)
                for p in still_alive:
                    p.kill()
            except psutil.NoSuchProcess:
                pass
        self.process.stdout.close()
        self.process = None


class TimeWorker(QThread):
    time_signal = pyqtSignal(float)

    def __init__(self, pause_time=0.1, parent=None):
        super().__init__(parent)
        self._stop_requested = False
        self.pause_time = pause_time

    def run(self):
        start_time = time.time()
        while not self._stop_requested:
            time.sleep(self.pause_time)
            self.time_signal.emit(time.time() - start_time)

    def stop(self):
        self._stop_requested = True


class AudioPlayWorker(QThread):
    finished_signal = pyqtSignal(str)
    packet_delay = pyqtSignal(float)

    def __init__(
        self,
        audio_path: str,
        streaming: bool,
        frames_per_buffer: int = 16384,
    ):
        super().__init__()
        self.audio_path = audio_path
        self.streaming = streaming
        self.frames_per_buffer = frames_per_buffer
        self.iterable_chunks = None

        self.is_interrupted = False
        self.elapsed = 0
        self.p = None
        self.stream = None

        self.time_worker = TimeWorker(pause_time=0.1)
        self.time_worker.time_signal.connect(self._calc_elapsed)

    def _calc_elapsed(self, elapsed):
        self.elapsed = elapsed
        self.packet_delay.emit(elapsed)

    def _initialize_audio_stream(self):
        p = pyaudio.PyAudio()
        stream = p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=44100,
            output=True,
            frames_per_buffer=self.frames_per_buffer,
        )
        return p, stream

    def start_audio_streaming(self):
        if self.streaming:
            self.p, self.stream = self._initialize_audio_stream()
            self.f = wave.open(self.audio_path, "wb")
            self.f.setnchannels(1)
            self.f.setsampwidth(2)
            self.f.setframerate(44100)
        else:
            self.f = open(self.audio_path, "wb")

    def audio_streaming(self):
        first_packet_time = None
        if not self.iterable_chunks:
            return
        for chunk in self.iterable_chunks:
            if self.is_interrupted:
                break
            if self.streaming:
                self.stream.write(chunk)
                self.f.writeframesraw(chunk)
            else:
                self.f.write(chunk)

            if first_packet_time is None:
                first_packet_time = self.elapsed
                self.time_worker.stop()

    async def async_audio_streaming(self):
        first_packet_time = None
        if not self.iterable_chunks:
            return
        async for chunk in self.iterable_chunks:
            if self.is_interrupted:
                break
            if self.streaming:
                self.stream.write(chunk)
                self.f.writeframesraw(chunk)
            else:
                self.f.write(chunk)

            if first_packet_time is None:
                first_packet_time = self.elapsed
                self.time_worker.stop()

    def stop_audio_streaming(self):
        if self.streaming and self.stream:
            self.stream.stop_stream()
            self.stream.close()
            self.p.terminate()
        self.f.close()
        logger.info("Playback Finished")

    def set_chunks(self, chunks: Iterator[bytes] | AsyncIterator[bytes] = None):
        self.iterable_chunks = chunks

    def run(self):
        logger.info("Sync Playback Started")
        self.start_audio_streaming()
        self.audio_streaming()
        self.stop_audio_streaming()
        if not self.is_interrupted:
            logger.info("Sync Playback Finished")
            self.finished_signal.emit(self.audio_path)

    async def run_async(self):
        logger.info("Async Playback Started")
        self.start_audio_streaming()
        await self.async_audio_streaming()
        self.stop_audio_streaming()
        if not self.is_interrupted:
            logger.info("Async Playback Finished")
            self.finished_signal.emit(self.audio_path)

    def stop(self):
        self.is_interrupted = True
        self.time_worker.stop()
        logger.info("Playback Stopped")


class TTSWorker(AudioPlayWorker):
    error_signal = pyqtSignal()

    def __init__(
        self,
        ref_files: List[str],
        ref_id: str,
        backend: str,
        text: str,
        api_key: str,
        audio_path: str,
        streaming: bool,
        **kwargs,
    ):
        super().__init__(audio_path, streaming)
        self.ref_files = ref_files
        self.ref_id = ref_id if ref_id else None
        self.backend = backend
        self.text = text
        self.api_key = api_key
        self.kwargs = kwargs
        self.streaming = streaming

    def _get_pre_files(self):
        return [f for f in self.ref_files if not f.endswith(".lab")]

    def _filter_audio_files(self, pre_files: List[str]):
        return [
            f
            for f in pre_files
            if Path(f).exists() and Path(f).with_suffix(".lab").exists()
        ]

    def _create_tts_request(self, audio_files: List[str]):
        return ServeTTSRequest(
            text=self.text,
            references=[
                ServeReferenceAudio(
                    audio=Path(f).read_bytes(),
                    text=Path(f).with_suffix(".lab").read_text(encoding="utf-8"),
                )
                for f in audio_files
            ],
            reference_id=self.ref_id,
            streaming=self.streaming,
            format=self.kwargs.get("format", "wav"),
            chunk_length=self.kwargs.get("chunk_length", 200),
            top_p=self.kwargs.get("top_p"),
            repetition_penalty=self.kwargs.get("repetition_penalty"),
            max_new_tokens=self.kwargs.get("max_new_tokens"),
            temperature=self.kwargs.get("temperature"),
            mp3_bitrate=self.kwargs.get("mp3_bitrate"),
        )

    def run(self):
        pre_files = self._get_pre_files()
        audio_files = self._filter_audio_files(pre_files)
        request = self._create_tts_request(audio_files)

        try:
            self.time_worker.start()
            response = requests.post(
                self.backend,
                data=ormsgpack.packb(request, option=ormsgpack.OPT_SERIALIZE_PYDANTIC),
                stream=self.streaming,
                headers={
                    "authorization": f"Bearer {self.api_key}",
                    "content-type": "application/msgpack",
                },
            )
            response.raise_for_status()
            audio_chunks = response.iter_content(chunk_size=self.frames_per_buffer)
            self.set_chunks(audio_chunks)
            super().run()
        except requests.RequestException as e:
            logger.error(f"Network request failed: {e}")
            self.error_signal.emit()
        finally:
            self.stop()  # Ensure the thread stops gracefully if there's an error
            response.close()


class AudioRecordWorker(AsyncTaskWorker):
    audio_data_signal = pyqtSignal(float)

    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        save_as_file: bool = False,
        output_file: str = None,
        ws_server_uri: str = None,
        parent=None,
    ):
        super().__init__(loop)
        self.mutex = QMutex()
        self.save_as_file = save_as_file
        self.output_file = output_file
        self.ws_client = WebSocketClient(ws_server_uri, loop) if ws_server_uri else None
        self.audio_data_buffer = io.BytesIO() if not self.output_file else None
        self.max_buffer_duration = 1
        self.sample_rate = config.sample_rate
        self.produce_loop = loop
        self.consume_loop = loop
        self.stop_data_event = asyncio.Event()

    async def _execute_task(self):
        await self._record_async()
        while not self.cancel_event.is_set():
            await asyncio.sleep(0.1)

    def cancel(self):
        if self.ws_client:
            close_task = self.consume_loop.create_task(
                self._wait_for_data_consumption_and_close()
            )
            self.consume_loop.create_task(
                self._wait_for_ws_close_and_cancel(close_task)
            )
        else:
            super().cancel()

    async def _wait_for_data_consumption_and_close(self):
        if self.ws_client:
            self.stop_data_event.set()
            while not self.ws_client.async_queue.empty():
                logger.info(
                    f"Waiting for {self.ws_client.async_queue.qsize()} items..."
                )
                await asyncio.sleep(0.1)
            await self.ws_client.close()
        else:
            logger.warning("No WebSocket client to close.")

    async def _wait_for_ws_close_and_cancel(self, close_task):
        await close_task
        super().cancel()

    async def _record_async(self):
        try:
            self._initialize_file_or_buffer()
            self.start_time = time.time()

            with sd.InputStream(
                callback=self._audio_callback,
                channels=1,
                samplerate=self.sample_rate,
                dtype="float32",
                blocksize=int(config.sample_frames * 0.1),
                device=config.input_device,
            ):
                if self.ws_client:
                    await self.ws_client.start()
                    self.consume_loop.create_task(self.ws_client.consume_data())

                await self._record_audio()

        except Exception as e:
            logger.error(f"Audio recording initialization failed: {e}")
        finally:
            if self.output_file and hasattr(self, "f"):
                self.f.close()

    def _initialize_file_or_buffer(self):
        if self.output_file:
            self.f = wave.open(self.output_file, "wb")
            self.f.setnchannels(1)
            self.f.setsampwidth(2)
            self.f.setframerate(self.sample_rate)
        else:
            self.audio_data_buffer.seek(0)

    async def _record_audio(self):
        """Main loop for audio recording."""
        while not self.stop_data_event.is_set():
            await asyncio.sleep(0.1)

    def _audio_callback(self, indata: np.ndarray, frames: int, _time, status):
        if status:
            logger.warning(f"Audio input error: {status}")

        audio_bytes = (indata[:, 0] * 32767).astype(np.int16).tobytes()

        if self.save_as_file:
            self._save_audio_data(audio_bytes)

        if not self.cancel_event.is_set():
            self.audio_data_signal.emit(time.time() - self.start_time)

        if not self.output_file:
            self._manage_audio_buffer(audio_bytes)

    def _manage_audio_buffer(self, audio_bytes):
        """Safely manage the audio buffer and produce data."""
        with QMutexLocker(self.mutex):
            self.produce_loop.create_task(self.ws_client.async_queue.put(audio_bytes))

    def _save_audio_data(self, audio_bytes):
        """Save audio data to the file safely."""
        with QMutexLocker(self.mutex):
            if self.output_file:
                self.f.writeframesraw(audio_bytes)
