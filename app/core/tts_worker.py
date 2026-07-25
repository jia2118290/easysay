"""
TTS 生成后台线程

要点：
  1. edge_tts 是纯在线服务，必须联网；这里对网络类异常单独识别，
     给 UI 层更精确的错误分类，而不是笼统地抛 "失败：xxx"
  2. 用 SubMaker/流式接口边收边写，配合 progress_signal 汇报真实进度，
     而不是"开始 0%，结束 100%"的假进度条
"""
import asyncio

from PySide6.QtCore import QThread, Signal
import edge_tts


class TTSWorker(QThread):
    # 生成完成：(success: bool, message: str)
    finished_signal = Signal(bool, str)
    # 进度百分比：0~100（估算值，基于已收到的音频字节数，非精确时长）
    progress_signal = Signal(int)

    # 粗略假设：正常语速下，每秒中文语音大概对应此字节数（用于估算总大小从而算百分比）
    _ESTIMATED_BYTES_PER_CHAR = 900

    def __init__(self, text: str, voice: str, rate: str, save_path: str):
        super().__init__()
        self.text = text
        self.voice = voice
        self.rate = rate
        self.save_path = save_path

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
        except Exception as e:  # noqa: BLE001 - 兜底捕获，避免线程崩溃
            self.finished_signal.emit(False, f"生成失败：{e}")

    async def _synthesize(self):
        communicate = edge_tts.Communicate(self.text, self.voice, rate=self.rate)
        estimated_total = max(len(self.text) * self._ESTIMATED_BYTES_PER_CHAR, 1)
        received = 0

        with open(self.save_path, "wb") as f:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    data = chunk["data"]
                    f.write(data)
                    received += len(data)
                    percent = min(int(received / estimated_total * 100), 99)
                    self.progress_signal.emit(percent)
        self.progress_signal.emit(100)
