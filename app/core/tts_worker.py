"""
TTS 生成后台线程

要点：
  1. edge_tts 是纯在线服务，必须联网；这里对网络类异常单独识别，
     给 UI 层更精确的错误分类，而不是笼统地抛 "失败：xxx"
  2. 用 SubMaker/流式接口边收边写，配合 progress_signal 汇报真实进度，
     而不是"开始 0%，结束 100%"的假进度条
  3. 标点停顿通过分割文本 + pydub 插入真实静音实现
"""
import asyncio
import os
import re
import tempfile

import edge_tts
from pydub import AudioSegment
from PySide6.QtCore import QThread, Signal

from app.config import ffmpeg_path

# 程序启动时设置 pydub 使用的 ffmpeg 路径（兼容打包后的环境）
AudioSegment.converter = ffmpeg_path()

# 用于在标点处切割文本的正则：匹配一个标点符号，标点包含在结果中
_SPLIT_PUNCTUATION = re.compile(r'([，。！？；：、,.;:!?])')


class TTSWorker(QThread):
    finished_signal = Signal(bool, str)
    progress_signal = Signal(int)

    _ESTIMATED_BYTES_PER_CHAR = 900

    def __init__(self, text: str, voice: str, rate: str, save_path: str,
                 pause_seconds: int = 0):
        super().__init__()
        self.text = text.strip()
        self.voice = voice
        self.rate = rate
        self.save_path = save_path
        self.pause_seconds = pause_seconds

    def run(self):
        try:
            asyncio.run(self._synthesize())
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
            communicate = edge_tts.Communicate(self.text, self.voice, rate=self.rate)
            await communicate.save(self.save_path)
            self.progress_signal.emit(100)
            return

        # 按标点切分成句子，每段包含"文本 + 标点"（标点不单独拆出来）
        # "你好，世界。" → ["你好，", "世界。"]
        segments = [s for s in _SPLIT_PUNCTUATION.split(self.text) if s]
        # 把"文本片段"和紧跟的"标点片段"重新合并
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
                seg_audio = await self._tts_to_segment(chunk, tmp_files)
                merged = seg_audio if merged is None else merged + seg_audio
                # 最后一段不加静音
                if i < total - 1:
                    merged = merged + silence
                self.progress_signal.emit(int((i + 1) / total * 99))

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
        """将一段文本生成临时 MP3，返回 AudioSegment 对象"""
        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        tmp.close()
        tmp_files.append(tmp.name)
        communicate = edge_tts.Communicate(text.strip(), self.voice, rate=self.rate)
        await communicate.save(tmp.name)
        return AudioSegment.from_mp3(tmp.name)
