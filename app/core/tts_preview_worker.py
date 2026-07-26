"""TTS 预览音频生成 Worker（试听 & 对比读参考音）"""
import asyncio
import tempfile

import edge_tts
from PySide6.QtCore import QThread, Signal


class PreviewWorker(QThread):
    finished_signal = Signal(bool, str)  # (success, temp_filepath_or_error_msg)

    def __init__(self, text: str, voice: str, rate: str):
        super().__init__()
        self.text = text
        self.voice = voice
        self.rate = rate

    def run(self):
        try:
            tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            tmp.close()
            asyncio.run(self._generate(tmp.name))
            self.finished_signal.emit(True, tmp.name)
        except Exception as e:  # noqa: BLE001
            self.finished_signal.emit(False, str(e))

    async def _generate(self, path: str):
        communicate = edge_tts.Communicate(self.text, self.voice, rate=self.rate)
        await communicate.save(path)
