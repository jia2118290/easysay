"""
均衡器动画组件 —— 本软件的"签名视觉元素"

生成音频时，用 5 根跳动的音柱替代平淡的进度条，呼应 Logo 里的声波图形，
让"正在生成语音"这件事被更直观地表达出来，而不是一条通用的加载条。

设计上保持克制：
  - 只有生成中才播放动画，静止状态收起为一条极细的基线
  - 颜色统一使用主题的琥珀色（accent-amber），不引入额外颜色
"""
import random

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QPainter, QColor, QLinearGradient, QBrush
from PySide6.QtWidgets import QWidget


class EqualizerWidget(QWidget):
    BAR_COUNT = 10
    ACCENT = QColor("#E8A33D")
    ACCENT_DIM = QColor("#3A3D46")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(40)
        self._levels = [0.15] * self.BAR_COUNT   # 当前高度比例 0~1
        self._targets = [0.15] * self.BAR_COUNT  # 动画目标高度
        self._active = False

        self._timer = QTimer(self)
        self._timer.setInterval(90)
        self._timer.timeout.connect(self._tick)

    def start(self):
        self._active = True
        self._timer.start()

    def stop(self):
        self._active = False
        self._timer.stop()
        self._levels = [0.15] * self.BAR_COUNT
        self._targets = [0.15] * self.BAR_COUNT
        self.update()

    def _tick(self):
        # 平滑插值靠近目标高度，快到达时重新随机一个新目标，制造律动感
        for i in range(self.BAR_COUNT):
            self._levels[i] += (self._targets[i] - self._levels[i]) * 0.4
            if abs(self._targets[i] - self._levels[i]) < 0.03:
                self._targets[i] = random.uniform(0.2, 1.0)
        self.update()

    def paintEvent(self, event):  # noqa: N802 (Qt 命名约定)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        width = self.width()
        height = self.height()
        gap = 6
        bar_width = (width - gap * (self.BAR_COUNT - 1)) / self.BAR_COUNT

        color = self.ACCENT if self._active else self.ACCENT_DIM

        for i, level in enumerate(self._levels):
            bar_height = max(4, height * level) if self._active else 3
            x = i * (bar_width + gap)
            y = (height - bar_height) / 2

            gradient = QLinearGradient(0, y, 0, y + bar_height)
            gradient.setColorAt(0, color.lighter(120))
            gradient.setColorAt(1, color)
            painter.setBrush(QBrush(gradient))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(int(x), int(y), int(bar_width), int(bar_height), 3, 3)
