import asyncio
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
    def __init__(self, loop: asyncio.AbstractEventLoop):
        super().__init__()
        self.loop = loop
        self._task = None
        self.cancel_event = asyncio.Event()

    def run(self):
        self._task = self.loop.create_task(self._execute_task())
        self._task.add_done_callback(self.on_task_done)
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

    def on_task_done(self, task: asyncio.Task):
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
        self.time_worker.time_signal.connect(self.calc_elapsed)

    def calc_elapsed(self, elapsed):
        self.elapsed = elapsed
        self.packet_delay.emit(elapsed)

    def initialize_audio_stream(self):
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
            self.p, self.stream = self.initialize_audio_stream()
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

    def get_pre_files(self):
        return [f for f in self.ref_files if not f.endswith(".lab")]

    def filter_audio_files(self, pre_files: List[str]):
        return [
            f
            for f in pre_files
            if Path(f).exists() and Path(f).with_suffix(".lab").exists()
        ]

    def create_tts_request(self, audio_files: List[str]):
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
        pre_files = self.get_pre_files()
        audio_files = self.filter_audio_files(pre_files)
        request = self.create_tts_request(audio_files)

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
        self.file_initialized = False
        self.output_file = output_file
        self.ws_client = WebSocketClient(ws_server_uri) if ws_server_uri else None
        self.async_queue = asyncio.Queue()

    async def _execute_task(self):
        await self.record_async()

    def cancel(self):
        self.cancel_event.set()
        self.loop.create_task(self.async_queue.put(None))
        super().cancel()

    async def record_async(self):
        try:
            # Open the output file once for the duration of recording
            self.f = wave.open(self.output_file, "wb")
            self.f.setnchannels(1)
            self.f.setsampwidth(2)  # 2 bytes for 16-bit audio
            self.f.setframerate(config.sample_rate)
            self.file_initialized = True
        except Exception as e:
            logger.error(f"Audio recording initialize failed!: {e}")
            self.file_initialized = False
            return  # Stop the thread if initialization fails

        self.start_time = time.time()

        with sd.InputStream(
            callback=self.audio_callback,
            channels=1,
            samplerate=config.sample_rate,
            dtype="float32",
            blocksize=int(config.sample_frames * 0.1),  # 0.1s
            device=config.input_device,
        ):
            if self.ws_client:
                await self.ws_client.start(self.async_queue)

            while not self.cancel_event.is_set():
                time.sleep(0.1)

        # Close the file once recording is stopped
        self.f.close()

    def audio_callback(self, indata: np.ndarray, frames: int, _time, status):
        if status:
            logger.warning(f"frames: {frames}, status: {status}")

        # self.input_wav[:frames] = indata[:, 0]
        audio_bytes = (indata[:, 0] * 32767).astype(np.int16).tobytes()

        self.loop.create_task(self.async_queue.put(audio_bytes))

        if self.save_as_file:
            self.save_audio_data(audio_bytes)

        if not self.cancel_event.is_set():
            self.audio_data_signal.emit(time.time() - self.start_time)

    def save_audio_data(self, audio_bytes):
        self.mutex.lock()
        try:
            if self.file_initialized:
                # logger.info(f"write: {len(audio_bytes)}")
                self.f.writeframesraw(audio_bytes)
        except IOError as e:
            logger.error(f"IO error saving audio data: {e}")
        except Exception as e:
            logger.error(f"General error saving audio data: {e}")
        finally:
            self.mutex.unlock()
