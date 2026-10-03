"""多人对话合成后台线程

逐行用各自说话人的音色合成台词，行间插入可选静音，最后用 pydub
拼接为单个 MP3。网络/取消/异常分类处理与单音色 TTSWorker 保持一致。
"""
import asyncio
import os
import tempfile

import edge_tts
from pydub import AudioSegment
from PySide6.QtCore import QThread, Signal

from app.config import ffmpeg_path

AudioSegment.converter = ffmpeg_path()


def _ensure_ffmpeg_env() -> None:
    """将打包后的 ffmpeg/ffprobe 目录追加到 PATH，确保 pydub 能找到。"""
    import sys
    if hasattr(sys, "_MEIPASS"):
        from pathlib import Path
        ffmpeg_dir = str(Path(sys._MEIPASS) / "ffmpeg")
        current_path = os.environ.get("PATH", "")
        if ffmpeg_dir not in current_path:
            os.environ["PATH"] = f"{ffmpeg_dir}{os.pathsep}{current_path}"


class MultiSpeakerWorker(QThread):
    finished_signal = Signal(bool, str)
    progress_signal = Signal(int)

    def __init__(self, lines: list[dict], save_path: str, pause_seconds: int = 0):
        """
        lines: [{"speaker": 角色名, "text": 台词, "voice": 音色, "rate": 语速}, ...]
        """
        super().__init__()
        self.lines = lines
        self.save_path = save_path
        self.pause_seconds = pause_seconds
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            _ensure_ffmpeg_env()
            AudioSegment.converter = ffmpeg_path()
            asyncio.run(self._synthesize())
            if self._cancelled:
                self.finished_signal.emit(False, "已取消生成")
            else:
                self.finished_signal.emit(True, f"生成成功：{self.save_path}")
        except edge_tts.exceptions.NoAudioReceived:
            self.finished_signal.emit(
                False, "未收到音频数据，可能是某句台词为空或音色暂不可用，请更换音色重试。"
            )
        except (ConnectionError, OSError) as e:
            self.finished_signal.emit(False, f"网络连接失败，请检查网络后重试：{e}")
        except Exception as e:  # noqa: BLE001
            self.finished_signal.emit(False, f"生成失败：{e}")

    async def _synthesize(self):
        total = len(self.lines)
        silence = AudioSegment.silent(duration=self.pause_seconds * 1000)
        merged: AudioSegment | None = None
        tmp_files: list[str] = []

        try:
            for i, line in enumerate(self.lines):
                if self._cancelled:
                    return
                text = line["text"].strip()
                if not text:
                    self.progress_signal.emit(int((i + 1) / total * 99))
                    continue
                seg = await self._tts_to_segment(
                    text, line["voice"], line["rate"], tmp_files
                )
                merged = seg if merged is None else merged + seg
                if i < total - 1 and self.pause_seconds > 0:
                    merged = merged + silence
                self.progress_signal.emit(int((i + 1) / total * 99))

            if self._cancelled:
                return
            if merged:
                merged.export(self.save_path, format="mp3")
            else:
                raise edge_tts.exceptions.NoAudioReceived
            self.progress_signal.emit(100)
        finally:
            for f in tmp_files:
                try:
                    os.remove(f)
                except OSError:
                    pass

    async def _tts_to_segment(self, text: str, voice: str, rate: str,
                              tmp_files: list[str]) -> AudioSegment:
        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        tmp.close()
        tmp_files.append(tmp.name)
        communicate = edge_tts.Communicate(text, voice, rate=rate)
        await communicate.save(tmp.name)
        return AudioSegment.from_mp3(tmp.name)
