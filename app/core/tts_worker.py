"""
TTS 生成后台线程

要点：
  1. edge_tts 是纯在线服务，必须联网；这里对网络类异常单独识别，
     给 UI 层更精确的错误分类，而不是笼统地抛 "失败：xxx"
  2. 流式模式通过 stream() 监听 WordBoundary 事件汇报真实合成进度
  3. 标点停顿通过分割文本 + pydub 插入真实静音实现
  4. cancel() 方法支持协作式取消
"""
import asyncio
import os
import re
import tempfile

import edge_tts
from pydub import AudioSegment
from PySide6.QtCore import QThread, Signal

from app.config import ffmpeg_path

AudioSegment.converter = ffmpeg_path()
# pydub 0.25+ 的 AudioSegment 没有 ffprobe 类属性，ffprobe 路径
# 通过 utils.get_prober_name() → which("ffprobe") 在 PATH 中查找。
# 打包后需要在 run() 时注入 PATH 环境变量，让 which() 能找到 ffprobe。
_SPLIT_PUNCTUATION = re.compile(r'([，。！？；：、,.;:!?])')


def _ensure_ffmpeg_env() -> None:
    """将打包后的 ffmpeg/ffprobe 目录追加到 PATH，确保 pydub 能找到。"""
    import sys
    if hasattr(sys, "_MEIPASS"):
        from pathlib import Path
        ffmpeg_dir = str(Path(sys._MEIPASS) / "ffmpeg")
        current_path = os.environ.get("PATH", "")
        if ffmpeg_dir not in current_path:
            os.environ["PATH"] = f"{ffmpeg_dir}{os.pathsep}{current_path}"


class TTSWorker(QThread):
    finished_signal = Signal(bool, str)
    progress_signal = Signal(int)

    def __init__(self, text: str, voice: str, rate: str, save_path: str,
                 pause_seconds: int = 0):
        super().__init__()
        self.text = text.strip()
        self.voice = voice
        self.rate = rate
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
                False, "未收到音频数据，可能是文本为空或该音色暂不可用，请更换音色重试。"
            )
        except (ConnectionError, OSError) as e:
            self.finished_signal.emit(False, f"网络连接失败，请检查网络后重试：{e}")
        except Exception as e:  # noqa: BLE001
            self.finished_signal.emit(False, f"生成失败：{e}")

    async def _synthesize(self):
        if self.pause_seconds <= 0:
            await self._synthesize_streaming()
            return
        await self._synthesize_with_pauses()

    async def _synthesize_streaming(self):
        """流式合成：通过 stream() 同时收集音频和监听 WordBoundary 进度"""
        communicate = edge_tts.Communicate(self.text, self.voice, rate=self.rate)
        estimated_words = max(1, len(re.findall(r'\S+', self.text)) or len(self.text))
        words_done = 0
        last_pct = 0
        audio_data: list[bytes] = []

        async for chunk in communicate.stream():
            if self._cancelled:
                return
            if chunk["type"] == "audio":
                audio_data.append(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                words_done += 1
                pct = min(99, max(1, int(words_done / estimated_words * 100)))
                if pct > last_pct:
                    last_pct = pct
                    self.progress_signal.emit(pct)

        if self._cancelled:
            return

        if audio_data:
            with open(self.save_path, "wb") as f:
                for data in audio_data:
                    f.write(data)

        self.progress_signal.emit(100)

    async def _synthesize_with_pauses(self):
        segments = [s for s in _SPLIT_PUNCTUATION.split(self.text) if s]
        chunks: list[str] = []
        buf = ""
        for s in segments:
            buf += s
            if len(s) == 1 and s in "，。！？；：、,.;:!?":
                chunks.append(buf)
                buf = ""
        if buf.strip():
            chunks.append(buf)

        if not chunks:
            return

        silence = AudioSegment.silent(duration=self.pause_seconds * 1000)
        merged: AudioSegment | None = None
        total = len(chunks)
        tmp_files: list[str] = []

        try:
            for i, chunk in enumerate(chunks):
                if self._cancelled:
                    return
                seg_audio = await self._tts_to_segment(chunk, tmp_files)
                merged = seg_audio if merged is None else merged + seg_audio
                if i < total - 1:
                    merged = merged + silence
                self.progress_signal.emit(int((i + 1) / total * 99))

            if self._cancelled:
                return
            if merged:
                merged.export(self.save_path, format="mp3")
            self.progress_signal.emit(100)
        finally:
            for f in tmp_files:
                try:
                    os.remove(f)
                except OSError:
                    pass

    async def _tts_to_segment(self, text: str, tmp_files: list[str]) -> AudioSegment:
        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        tmp.close()
        tmp_files.append(tmp.name)
        communicate = edge_tts.Communicate(text.strip(), self.voice, rate=self.rate)
        await communicate.save(tmp.name)
        return AudioSegment.from_mp3(tmp.name)
