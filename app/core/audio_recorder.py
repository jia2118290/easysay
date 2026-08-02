"""麦克风录音 Worker（16kHz 16-bit mono WAV）"""
import os
import tempfile
import wave

from PySide6.QtCore import QThread, Signal


class AudioRecorder(QThread):
    finished_signal = Signal(bool, str)  # (success, wav_path_or_error)

    def __init__(self, sample_rate: int = 16000, save_dir: str = ""):
        super().__init__()
        self.sample_rate = sample_rate
        self.save_dir = save_dir
        self.stop_requested = False
        self._audio_buffer: bytearray | None = None
        self._wav_path: str = ""

    def _audio_callback(self, indata: bytes, _frames: int, _time_info, status):
        if status:
            print(f"[AudioRecorder] status: {status}")
        if self._audio_buffer is not None:
            self._audio_buffer.extend(indata)

    def run(self):
        import sounddevice as sd

        self._audio_buffer = bytearray()
        self.stop_requested = False

        try:
            stream = sd.RawInputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype="int16",
                callback=self._audio_callback,
            )
        except sd.PortAudioError as e:
            msg = str(e)
            if "permission" in msg.lower() or "access" in msg.lower() or \
               "authorization" in msg.lower() or "denied" in msg.lower():
                self.finished_signal.emit(
                    False,
                    "麦克风权限被拒绝：请在 系统设置 → 隐私与安全性 → 麦克风 中允许本应用访问麦克风",
                )
            else:
                self.finished_signal.emit(False, f"无法打开麦克风设备：{e}")
            return
        except Exception as e:  # noqa: BLE001
            self.finished_signal.emit(False, f"录音初始化失败：{e}")
            return

        with stream:
            while not self.stop_requested:
                sd.sleep(100)

        if self._audio_buffer is None or len(self._audio_buffer) == 0:
            self.finished_signal.emit(False, "未录制到任何音频，请检查麦克风连接和权限")
            return

        self._wav_path = self._create_wav_path()
        try:
            with wave.open(self._wav_path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)  # 16-bit
                wf.setframerate(self.sample_rate)
                wf.writeframes(bytes(self._audio_buffer))
        except Exception as e:  # noqa: BLE001
            self._cleanup_wav()
            self.finished_signal.emit(False, f"保存录音文件失败：{e}")
            return

        self.finished_signal.emit(True, self._wav_path)

    def _create_wav_path(self) -> str:
        if self.save_dir and os.path.isdir(self.save_dir):
            import time
            timestamp = int(time.time() * 1000)
            return os.path.join(self.save_dir, f"easysay_recording_{timestamp}.wav")

        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.close()
        return tmp.name

    def _cleanup_wav(self):
        if self._wav_path and os.path.exists(self._wav_path):
            try:
                os.remove(self._wav_path)
            except OSError:
                pass

    def get_wav_path(self) -> str:
        return self._wav_path

    def stop(self):
        self.stop_requested = True
