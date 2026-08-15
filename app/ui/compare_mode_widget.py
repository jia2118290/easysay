"""对比读模式 Widget

流程：粘贴文案 → 拆分句子 → 系统朗读当前句 → 等待 1 秒 → 用户跟读录音
→ 点击停止录音 → Azure 评分 → 显示结果 → 自动跳下一句
"""
import os
import re

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QListWidget, QListWidgetItem,
    QLabel, QSplitter, QMessageBox,
)
from PySide6.QtMultimedia import QMediaPlayer

from app.core.settings_manager import SettingsManager
from app.core.tts_preview_worker import PreviewWorker
from app.core.audio_recorder import AudioRecorder
from app.core.pronunciation_worker import PronunciationWorker
from app.ui.azure_settings_dialog import AzureSettingsDialog
from app.ui.equalizer_widget import EqualizerWidget

_SPLIT_RE = re.compile(r'(?<=[。！？.!?\n])\s*')

_BADGE_COLORS = [
    (90, "scoreBadgeGreen"),
    (80, "scoreBadgeDarkGreen"),
    (70, "scoreBadgeOrange"),
    (60, "scoreBadgeYellow"),
    (0, "scoreBadgeRed"),
]


class CompareModeWidget(QWidget):
    def __init__(self, media_player: QMediaPlayer, parent=None):
        super().__init__(parent)
        self._media_player = media_player
        self.settings = SettingsManager()
        # 确保主窗口与对比读共用同一个 SettingsManager 实例
        if parent:
            parent_settings = getattr(parent, "settings", None)
            if parent_settings:
                self.settings = parent_settings

        self.sentences: list[str] = []
        self.scores: dict[int, dict] = {}
        self.current_idx: int = -1
        self.is_flow_active: bool = False

        self._preview_worker: PreviewWorker | None = None
        self._recorder: AudioRecorder | None = None
        self._pron_worker: PronunciationWorker | None = None
        self._tts_tmp: str | None = None
        self._wav_tmp: str | None = None

        self._voice_name: str = "请选择"
        self._voice_rate: str = "+0%"
        self._voice_lang: str = ""

        self._is_recording: bool = False
        self._is_scoring: bool = False

        self._build_ui()
        self._connect_signals()

    def set_voice_params(self, voice: str, rate: str, language: str):
        self._voice_name = voice
        self._voice_rate = rate
        self._voice_lang = language

    def abort_flow(self):
        self.is_flow_active = False
        self._is_recording = False
        self._is_scoring = False
        if self._preview_worker and self._preview_worker.isRunning():
            self._preview_worker.terminate()
        if self._recorder and self._recorder.isRunning():
            self._recorder.stop()
            self._recorder.wait(3000)
        if self._pron_worker and self._pron_worker.isRunning():
            self._pron_worker.terminate()
        self._media_player.stop()
        self._cleanup_temps()
        self._set_idle_state()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 4, 0, 0)
        root.setSpacing(10)

        # --- 顶部：粘贴区域 + 拆分按钮 ---
        paste_row = QVBoxLayout()
        paste_row.setSpacing(6)

        self.text_area = QTextEdit()
        self.text_area.setObjectName("compareTextArea")
        self.text_area.setPlaceholderText("请粘贴需要对比朗读的文本，系统将自动按句子拆分...")
        self.text_area.setMaximumHeight(120)

        split_row = QHBoxLayout()
        split_row.setSpacing(8)
        self.label_sentence_count = QLabel("共 0 句")
        self.label_sentence_count.setObjectName("charCountLabel")
        self.btn_split = QPushButton("拆分句子")
        self.btn_split.setObjectName("secondaryButton")
        self.btn_split.clicked.connect(self._split_and_reload)

        split_row.addWidget(self.label_sentence_count)
        split_row.addStretch()
        split_row.addWidget(self.btn_split)

        paste_row.addWidget(self.text_area)
        paste_row.addLayout(split_row)

        # --- 中间：句子列表 + 评分面板 ---
        splitter = QSplitter(Qt.Horizontal)

        self.sentence_list = QListWidget()
        self.sentence_list.setObjectName("sentenceList")
        self.sentence_list.currentRowChanged.connect(self._on_sentence_selected)

        # 右侧评分面板
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(8, 0, 0, 0)
        right_layout.setSpacing(8)

        self.current_sentence_label = QLabel("请在左侧选择句子，然后点击「开始」")
        self.current_sentence_label.setObjectName("currentSentenceLabel")
        self.current_sentence_label.setWordWrap(True)
        self.current_sentence_label.setAlignment(Qt.AlignCenter)

        self.score_value_label = QLabel("--")
        self.score_value_label.setObjectName("scoreValueLabel")
        self.score_value_label.setAlignment(Qt.AlignCenter)

        self.score_detail_label = QLabel("准确度 / 流利度 / 完整度 / 语调")
        self.score_detail_label.setObjectName("scoreDetailLabel")
        self.score_detail_label.setAlignment(Qt.AlignCenter)

        self.equalizer = EqualizerWidget()
        self.equalizer.setFixedHeight(40)

        self.status_label = QLabel("就绪")
        self.status_label.setObjectName("status_label")
        self.status_label.setAlignment(Qt.AlignCenter)

        self.error_label = QLabel()
        self.error_label.setObjectName("errorLabel")
        self.error_label.setVisible(False)
        self.error_label.setAlignment(Qt.AlignCenter)

        right_layout.addWidget(self.current_sentence_label)
        right_layout.addWidget(self.score_value_label)
        right_layout.addWidget(self.score_detail_label)
        right_layout.addStretch()
        right_layout.addWidget(self.equalizer)
        right_layout.addWidget(self.status_label)
        right_layout.addWidget(self.error_label)

        splitter.addWidget(self.sentence_list)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        # --- 底部按钮栏 ---
        btn_bar = QHBoxLayout()
        btn_bar.setSpacing(8)

        self.btn_prev = QPushButton("◀  上一句")
        self.btn_prev.setObjectName("secondaryButton")
        self.btn_prev.clicked.connect(self._prev_sentence)

        self.btn_next = QPushButton("下一句  ▶")
        self.btn_next.setObjectName("secondaryButton")
        self.btn_next.clicked.connect(self._next_sentence)

        self.btn_start = QPushButton("▶  开始")
        self.btn_start.setObjectName("generateButton")
        self.btn_start.clicked.connect(self._start_flow)

        self.btn_stop = QPushButton("■  停止")
        self.btn_stop.setObjectName("secondaryButton")
        self.btn_stop.clicked.connect(self._stop_flow)
        self.btn_stop.setVisible(False)

        self.btn_settings = QPushButton("⚙  设置")
        self.btn_settings.setObjectName("settingsButton")
        self.btn_settings.clicked.connect(self._open_settings)

        btn_bar.addWidget(self.btn_prev)
        btn_bar.addWidget(self.btn_next)
        btn_bar.addStretch()
        btn_bar.addWidget(self.btn_start)
        btn_bar.addWidget(self.btn_stop)
        btn_bar.addWidget(self.btn_settings)

        root.addLayout(paste_row)
        root.addWidget(splitter, stretch=1)
        root.addLayout(btn_bar)

    def _connect_signals(self):
        # 文本变化时自动拆分（用 timer 做 debounce）
        self._split_timer = QTimer(self)
        self._split_timer.setSingleShot(True)
        self._split_timer.setInterval(600)
        self._split_timer.timeout.connect(self._split_and_reload)
        self.text_area.textChanged.connect(lambda: self._split_timer.start())

    # ------------------------------------------------------------------
    # 句子管理
    # ------------------------------------------------------------------
    def _split_and_reload(self):
        self._split_timer.stop()
        text = self.text_area.toPlainText().strip()
        # 去掉空行：多个连续换行 → 单个换行
        text = re.sub(r'\n{2,}', '\n', text)
        # 只含空白字符的行 → 删除
        text = re.sub(r'\n[ \t]*\n', '\n', text)
        if not text:
            self.sentences = []
            self._rebuild_list()
            self.label_sentence_count.setText("共 0 句")
            return

        raw = _SPLIT_RE.split(text)
        self.sentences = [s.strip() for s in raw if s.strip()]
        self.scores.clear()
        self.current_idx = 0 if self.sentences else -1
        self._rebuild_list()
        self._show_current_sentence()

        count = len(self.sentences)
        self.label_sentence_count.setText(f"共 {count} 句")

    def _rebuild_list(self):
        self.sentence_list.blockSignals(True)
        self.sentence_list.clear()
        for i, s in enumerate(self.sentences):
            text = s[:60] + ("..." if len(s) > 60 else "")
            badge = self._score_badge(i)
            item = QListWidgetItem(f"句 {i + 1}：{badge}{text}")
            self.sentence_list.addItem(item)
        if 0 <= self.current_idx < self.sentence_list.count():
            self.sentence_list.setCurrentRow(self.current_idx)
        self.sentence_list.blockSignals(False)

    def _score_badge(self, idx: int) -> str:
        if idx not in self.scores:
            return "[--] "
        score = self.scores[idx].get("overall", 0)
        return f"[{int(score)}] "

    def _on_sentence_selected(self, row: int):
        if row < 0 or row >= len(self.sentences):
            return
        self.current_idx = row
        self._show_current_sentence()

    def _prev_sentence(self):
        if self.current_idx > 0:
            self.current_idx -= 1
            self.sentence_list.setCurrentRow(self.current_idx)
            self._show_current_sentence()

    def _next_sentence(self):
        if self.current_idx < len(self.sentences) - 1:
            self.current_idx += 1
            self.sentence_list.setCurrentRow(self.current_idx)
            self._show_current_sentence()

    def _show_current_sentence(self):
        self._clear_error()
        if self.current_idx < 0 or self.current_idx >= len(self.sentences):
            self.current_sentence_label.setText("请在左侧选择句子，然后点击「开始」")
            self.score_value_label.setText("--")
            self.score_value_label.setStyleSheet("")
            self.score_detail_label.setText("")
            return

        self.current_sentence_label.setText(self.sentences[self.current_idx])

        if self.current_idx in self.scores:
            s = self.scores[self.current_idx]
            self._display_score(s)
        else:
            self.score_value_label.setText("--")
            self.score_value_label.setStyleSheet("")
            self.score_detail_label.setText("准确度 / 流利度 / 完整度 / 语调")
            self.score_detail_label.setStyleSheet("")
            self.current_sentence_label.setText(self.sentences[self.current_idx])

    # ------------------------------------------------------------------
    # 开始 / 停止 流程
    # ------------------------------------------------------------------
    def _start_flow(self):
        self._clear_error()

        if not self.sentences:
            QMessageBox.warning(self, "提示", "请先粘贴文本并拆分句子")
            return
        if self.current_idx < 0 or self.current_idx >= len(self.sentences):
            QMessageBox.warning(self, "提示", "请先在左侧列表中选择一个句子")
            return
        if self._voice_name == "请选择" or not self._voice_name:
            QMessageBox.warning(self, "提示",
                "请先在顶部「音色设置」中选择语言、性别和音色")
            return

        key = self.settings.get("azure_speech_key") or ""
        region = self.settings.get("azure_speech_region") or ""
        if not key:
            QMessageBox.warning(self, "提示",
                "请先配置 Azure 语音服务\n点击底部「⚙ 设置」按钮，输入 API Key 和 Region")
            return

        self.is_flow_active = True
        self._set_active_state()
        self._process_current_sentence()

    def _stop_flow(self):
        # 录音阶段：停止录音，保留 is_flow_active，等待评分回显
        if self._is_recording and self._recorder and self._recorder.isRunning():
            self._recorder.stop()
            self.status_label.setText("正在停止录音并提交评分...")
            return

        # 评分阶段：已提交，等结果即可，不强制中止
        if self._is_scoring:
            return

        # 其余阶段（TTS 生成 / 朗读中）：直接中止
        self.is_flow_active = False
        self._media_player.stop()
        if self._preview_worker and self._preview_worker.isRunning():
            self._preview_worker.terminate()
        self._cleanup_temps()
        self._set_idle_state()
        self.status_label.setText("已停止")

    def _process_current_sentence(self):
        """生成参考音 → 播放 → 1秒后录音 → 评分"""
        self._clear_error()
        sentence = self.sentences[self.current_idx]
        self.status_label.setText(f"正在生成参考发音...（第 {self.current_idx + 1}/{len(self.sentences)} 句）")
        self.equalizer.start()

        self._preview_worker = PreviewWorker(sentence, self._voice_name, self._voice_rate)
        self._preview_worker.finished_signal.connect(self._on_tts_ready)
        self._preview_worker.start()

    def _on_tts_ready(self, success: bool, msg: str):
        self.equalizer.stop()
        if not self.is_flow_active:
            self._cleanup_temp_file(msg)
            return
        if not success:
            self._show_error(f"生成参考发音失败：{msg}")
            self._set_idle_state()
            return
        self._tts_tmp = msg
        self.status_label.setText("正在朗读参考发音...")
        self._media_player.setSource(QUrl.fromLocalFile(msg))
        try:
            self._media_player.mediaStatusChanged.disconnect(self._on_media_status)
        except RuntimeError:
            pass
        self._media_player.mediaStatusChanged.connect(self._on_media_status)
        self._media_player.play()

    def _on_media_status(self, status):
        if status != QMediaPlayer.MediaStatus.EndOfMedia:
            return
        if not self.is_flow_active:
            return
        self.status_label.setText("准备录音...")
        QTimer.singleShot(1000, self._start_recording)

    def _start_recording(self):
        if not self.is_flow_active:
            return
        self._is_recording = True
        self.status_label.setText(f"正在录音，请朗读...（第 {self.current_idx + 1}/{len(self.sentences)} 句）")
        self.equalizer.start()

        audio_dir = self.settings.get("azure_audio_dir") or ""
        self._recorder = AudioRecorder(sample_rate=16000, save_dir=audio_dir)
        self._recorder.finished_signal.connect(self._on_recording_done)
        self._recorder.start()

    def _on_recording_done(self, success: bool, msg: str):
        self.equalizer.stop()
        self._is_recording = False

        if not self.is_flow_active:
            self._cleanup_temp_file(msg)
            return
        if not success:
            self._show_error(f"录音失败：{msg}")
            self._set_idle_state()
            return

        self._wav_tmp = msg
        self._is_scoring = True
        sentence = self.sentences[self.current_idx]

        self.status_label.setText(f"正在评分...（第 {self.current_idx + 1}/{len(self.sentences)} 句）")
        key = self.settings.get("azure_speech_key") or ""
        region = self.settings.get("azure_speech_region") or ""

        self._pron_worker = PronunciationWorker(self._wav_tmp, sentence, key, region)
        self._pron_worker.finished_signal.connect(self._on_scoring_done)
        self._pron_worker.start()

    def _on_scoring_done(self, success: bool, data: dict):
        self.equalizer.stop()
        self._is_scoring = False
        self._cleanup_temps()

        if not success:
            if self.is_flow_active:
                self._show_error(f"评分失败：{data.get('error', '未知错误')}")
                self._set_idle_state()
            return

        self.scores[self.current_idx] = data
        self._rebuild_list()
        self.sentence_list.setCurrentRow(self.current_idx)
        self._display_score(data)

        if self.is_flow_active and self.current_idx + 1 < len(self.sentences):
            self.current_idx += 1
            self.status_label.setText(f"得分已保存，2 秒后进入下一句...（第 {self.current_idx + 1}/{len(self.sentences)} 句）")
            QTimer.singleShot(2000, self._advance_to_next)
        else:
            self.is_flow_active = False
            self._set_idle_state()
            self.status_label.setText("全部句子评测完成！")

    def _advance_to_next(self):
        if not self.is_flow_active:
            return
        self.sentence_list.setCurrentRow(self.current_idx)
        self._process_current_sentence()

    # ------------------------------------------------------------------
    # 评分显示
    # ------------------------------------------------------------------
    def _display_score(self, scores: dict):
        overall = scores.get("overall", 0)
        accuracy = scores.get("accuracy", 0)
        fluency = scores.get("fluency", 0)
        completeness = scores.get("completeness", 0)
        prosody = scores.get("prosody", 0)
        words = scores.get("words", [])

        color = _get_score_color(overall)
        self.score_value_label.setText(str(int(overall)))
        self.score_value_label.setStyleSheet(
            f"QLabel {{ color: {color}; font-size: 52pt; font-weight: bold; "
            f"font-family: 'JetBrains Mono', 'SF Mono', 'Consolas', monospace; }}"
        )
        self.score_detail_label.setText(
            f"准确度 {int(accuracy)}  |  流利度 {int(fluency)}  "
            f"|  完整度 {int(completeness)}  |  语调 {int(prosody)}"
        )
        self.status_label.setText(f"得分：{int(overall)}")

        self._show_word_highlights(words)

    def _show_word_highlights(self, words: list[dict]):
        sentence = self.sentences[self.current_idx]
        if not words:
            self.current_sentence_label.setText(sentence)
            return

        parts = []
        ref_text = sentence
        pos = 0

        for w in words:
            word = w.get("word", "")
            w_acc = w.get("accuracy", 0)
            w_err = w.get("error_type", "")

            idx = ref_text.find(word, pos)
            if idx > pos:
                parts.append(_plain_span(ref_text[pos:idx]))
            elif idx == -1:
                continue

            parts.append(_word_span(word, w_acc, w_err))
            pos = idx + len(word)

        if pos < len(ref_text):
            parts.append(_plain_span(ref_text[pos:]))

        self.current_sentence_label.setText("<p>" + "".join(parts) + "</p>")

    # ------------------------------------------------------------------
    # 状态切换
    # ------------------------------------------------------------------
    def _set_active_state(self):
        self.btn_start.setVisible(False)
        self.btn_stop.setVisible(True)
        self.btn_prev.setEnabled(False)
        self.btn_next.setEnabled(False)
        self.text_area.setEnabled(False)
        self.btn_split.setEnabled(False)
        self.status_label.setText("开始处理...")

    def _set_idle_state(self):
        self.btn_start.setVisible(True)
        self.btn_stop.setVisible(False)
        self.btn_prev.setEnabled(True)
        self.btn_next.setEnabled(True)
        self.text_area.setEnabled(True)
        self.btn_split.setEnabled(True)

    # ------------------------------------------------------------------
    # 工具方法
    # ------------------------------------------------------------------
    def _open_settings(self):
        AzureSettingsDialog(self).exec()

    def _show_error(self, msg: str):
        self.error_label.setText("⚠ " + msg)
        self.error_label.setVisible(True)

    def _clear_error(self):
        self.error_label.setVisible(False)

    def _cleanup_temps(self):
        if self._tts_tmp and os.path.exists(self._tts_tmp):
            try:
                os.remove(self._tts_tmp)
            except OSError:
                pass
        self._tts_tmp = None
        if self._wav_tmp and os.path.exists(self._wav_tmp):
            try:
                os.remove(self._wav_tmp)
            except OSError:
                pass
        self._wav_tmp = None

    @staticmethod
    def _cleanup_temp_file(path: str):
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass


def _get_score_color(score: float) -> str:
    if score >= 90:
        return "#4ADE80"
    elif score >= 80:
        return "#22C55E"
    elif score >= 70:
        return "#F59E0B"
    elif score >= 60:
        return "#EAB308"
    else:
        return "#E5484D"


def _word_span(word: str, accuracy: float, error_type: str) -> str:
    if error_type == "None" or not error_type:
        # 发音准确：绿色
        return f'<span style="color:#4ADE80;">{word}</span>'

    if accuracy >= 80:
        c = "#F59E0B"
    elif accuracy >= 60:
        c = "#EAB308"
    else:
        c = "#E5484D"

    if error_type == "Omission":
        return f'<span style="color:{c}; text-decoration:underline;">{word}</span>'
    else:
        return f'<span style="color:{c}; font-weight:bold;">{word}</span>'


def _plain_span(text: str) -> str:
    return f'<span style="color:#6C6F78;">{text}</span>'
