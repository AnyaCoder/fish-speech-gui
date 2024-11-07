import os

os.environ["no_proxy"] = "localhost, 127.0.0.1, 0.0.0.0"
import re
import subprocess
import time
import wave
from pathlib import Path

import httpx
import ormsgpack
import psutil
import pyaudio
from PyQt6.QtCore import QMutex, QMutexLocker, QThread, pyqtSignal

from fish.modules.log import logger
from fish.utils.audio import ServeReferenceAudio, ServeTTSRequest
from fish.utils.i18n import _t

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
        self.start_time = time.time()
        self._stop_requested = False
        self.pause_time = pause_time

    def run(self):
        while not self._stop_requested:
            time.sleep(self.pause_time)
            self.time_signal.emit(time.time() - self.start_time)

    def stop(self):
        self._stop_requested = True


class TTSWorker(BaseWorker):
    packet_delay = pyqtSignal(float)

    def __init__(
        self,
        ref_files: list[str],
        ref_id: str,
        backend: str,
        text: str,
        api_key: str,
        audio_path: str,
        **kwargs,
    ):
        super().__init__()

        self.ref_files = ref_files
        self.ref_id = ref_id if len(ref_id) > 0 else None
        self.backend = backend
        self.text = text
        self.api_key = api_key
        self.audio_path = audio_path
        self.kwargs = kwargs
        self.time_worker = TimeWorker(pause_time=0.1)
        self.time_worker.time_signal.connect(self.calc_elapsed)
        self.elapsed = 0

    def calc_elapsed(self, elapsed):
        self.elapsed = elapsed
        self.packet_delay.emit(elapsed)

    def run(self):
        self._process_audio_stream()

    def _process_audio_stream(self):
        pre_files = self.get_pre_files()
        audio_files = self.filter_audio_files(pre_files)
        streaming = self.kwargs.get("stream", False)
        request = self.create_tts_request(audio_files, streaming)
        frames_per_buffer = 16384
        first_packet_time = None

        self.time_worker.start()

        if streaming:
            p, stream = self.initialize_audio_stream(frames_per_buffer)
            self.p = p
            self.stream = stream
            f = wave.open(self.audio_path, "wb")
            f.setnchannels(1)
            f.setsampwidth(2)
            f.setframerate(44100)
        else:
            f = open(self.audio_path, "wb")

        self.f = f
        with httpx.Client() as client:
            with client.stream(
                "POST",
                self.backend,
                content=ormsgpack.packb(
                    request, option=ormsgpack.OPT_SERIALIZE_PYDANTIC
                ),
                headers={
                    "authorization": f"Bearer {self.api_key}",
                    "content-type": "application/msgpack",
                },
                timeout=None,
            ) as response:
                for chunk in response.iter_bytes(chunk_size=frames_per_buffer):
                    if first_packet_time is None:
                        first_packet_time = self.elapsed
                        self.time_worker.stop()

                    if self.is_interrupted:
                        return

                    if streaming:
                        stream.write(chunk)
                        f.writeframesraw(chunk)
                    else:
                        f.write(chunk)

        self.finish()

        if not self.is_interrupted:
            self.finished_signal.emit(self.audio_path)

    def get_pre_files(self):
        return [f for f in self.ref_files if not f.endswith(".lab")]

    def filter_audio_files(self, pre_files: list):
        return [
            f
            for f in pre_files
            if Path(f).exists() and Path(f).with_suffix(".lab").exists()
        ]

    def create_tts_request(self, audio_files: list, streaming: bool):
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
            streaming=streaming,
            format="wav" if streaming else "mp3",
            chunk_length=self.kwargs.get("chunk_length"),
            top_p=self.kwargs.get("top_p"),
            repetition_penalty=self.kwargs.get("repetition_penalty"),
            max_new_tokens=self.kwargs.get("max_new_tokens"),
            temperature=self.kwargs.get("temperature"),
            mp3_bitrate=self.kwargs.get("mp3_bitrate"),
        )

    def initialize_audio_stream(self, frames_per_buffer: int):
        p = pyaudio.PyAudio()
        stream = p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=44100,
            output=True,
            frames_per_buffer=frames_per_buffer,
        )
        return p, stream

    def stop(self):
        self.is_interrupted = True
        logger.info("Stop requested!")
        self.finish()

    def finish(self):
        streaming = self.kwargs.get("stream", False)
        if streaming:
            self.stream.stop_stream()
            self.stream.close()
            self.p.terminate()
            logger.warning("Stop streaming!")
        self.time_worker.stop()
        logger.info("Timer off!")
        self.f.close()
        logger.info("File closed!")
