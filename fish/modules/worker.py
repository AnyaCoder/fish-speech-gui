import os

os.environ["no_proxy"] = "localhost, 127.0.0.1, 0.0.0.0"
import re
import subprocess
from pathlib import Path

import httpx
import ormsgpack
import psutil
from PyQt6.QtCore import QMutex, QMutexLocker, QThread, QWaitCondition, pyqtSignal

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


class TTSWorker(QThread):
    finished = pyqtSignal()

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
        self.mutex = QMutex()
        self.wait_condition = QWaitCondition()
        self._stop_requested = False
        self.ref_files = ref_files
        self.ref_id = ref_id if len(ref_id) > 0 else None
        self.backend = backend
        self.text = text
        self.api_key = api_key
        self.audio_path = audio_path
        self.kwargs = kwargs

    def run(self):
        pre_files = [f for f in self.ref_files if not f.endswith(".lab")]
        audio_files = [
            f
            for f in pre_files
            if Path(f).exists() and Path(f).with_suffix(".lab").exists()
        ]

        request = ServeTTSRequest(
            text=self.text,
            references=[
                ServeReferenceAudio(
                    audio=Path(f).read_bytes(),
                    text=Path(f).with_suffix(".lab").read_text(encoding="utf-8"),
                )
                for f in audio_files
            ],
            reference_id=self.ref_id,
            streaming=False,
            format="mp3",
            chunk_length=self.kwargs["chunk_length"],
            top_p=self.kwargs["top_p"],
            repetition_penalty=self.kwargs["repetition_penalty"],
            max_new_tokens=self.kwargs["max_new_tokens"],
            temperature=self.kwargs["temperature"],
            mp3_bitrate=self.kwargs["mp3_bitrate"],
        )

        with httpx.Client() as client, open(f"{self.audio_path}", "wb") as f:
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
                for chunk in response.iter_bytes():
                    self.mutex.lock()
                    if self._stop_requested:
                        print("TTS is interrupted!")
                        self.mutex.unlock()
                        break
                    self.mutex.unlock()
                    f.write(chunk)

        self.finished.emit()

    def stop(self):
        self.mutex.lock()
        self._stop_requested = True
        self.mutex.unlock()
        self.wait_condition.wakeAll()
