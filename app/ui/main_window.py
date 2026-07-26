"""EasySay 主窗口"""
import os
import re
import subprocess
import platform
import tempfile
import asyncio

from PySide6.QtCore import Qt, QThread, Signal, QUrl
from PySide6.QtGui import QIcon, QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QLineEdit, QPushButton, QComboBox, QLabel, QFileDialog,
    QMessageBox, QGroupBox, QMenuBar, QApplication,
)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

import edge_tts

from app.config import APP_DISPLAY_NAME, APP_ICON_PATH, DARK_QSS_PATH
from app.core.settings_manager import SettingsManager
from app.core.tts_worker import TTSWorker
from app.core.validator import validate_text_language, format_errors
from app.core.voice_repository import VoiceRepository
from app.ui.about_dialog import AboutDialog
from app.ui.equalizer_widget import EqualizerWidget

PLACEHOLDER = "请选择"

# 各语种的试听文本
_PREVIEW_TEXTS = {
    "中文 (zh)": "你好，我是一直要求进步的昌强同学。",
    "英语 (en)": "Hello, I'm Changqiang, always striving to improve.",
    "日语 (ja)": "こんにちは、私はいつも進歩を求める昌強です。",
    "韩语 (ko)": "안녕하세요, 저는 항상 진보를 추구하는 창창입니다.",
    "法语 (fr)": "Bonjour, je suis Changqiang, toujours en quête de progrès.",
    "意大利语 (it)": "Ciao, sono Changqiang, sempre alla ricerca del progresso.",
    "西班牙语 (es)": "Hola, soy Changqiang, siempre buscando progresar.",
}

# 各语种朗读速度（字符/秒），用于估算生成时长
_CHAR_PER_SECOND = {
    "中文 (zh)": 3.5,
    "英语 (en)": 4.5,
    "日语 (ja)": 3.0,
    "韩语 (ko)": 3.5,
    "法语 (fr)": 4.5,
    "意大利语 (it)": 4.5,
    "西班牙语 (es)": 4.5,
}
_DEFAULT_CPS = 4.0

_RATE_PATTERN = re.compile(r'^[+-]\d{1,2}%$')


class PreviewWorker(QThread):
    """后台线程：生成试听音频到临时文件，完成后通知 UI 播放"""
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


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_DISPLAY_NAME)
        self.setWindowIcon(QIcon(APP_ICON_PATH))

        screen = QApplication.primaryScreen()
        if screen:
            sz = screen.availableSize()
            self.resize(int(sz.width() * 0.65), int(sz.height() * 0.75))
        else:
            self.resize(1280, 960)

        self.voice_repo = VoiceRepository()
        self.settings = SettingsManager()
        self.output_dir = self.settings.get("last_output_dir") or ""
        self.worker: TTSWorker | None = None
        self.preview_worker: PreviewWorker | None = None
        self._preview_tmp: str | None = None
        self._last_generated_path: str | None = None

        self._audio_output = QAudioOutput()
        self._media_player = QMediaPlayer()
        self._media_player.setAudioOutput(self._audio_output)

        self._load_stylesheet()
        self._build_menu()
        self._build_ui()
        self._build_shortcuts()
        self._restore_settings()

    # ------------------------------------------------------------------
    # 初始化 UI
    # ------------------------------------------------------------------
    def _load_stylesheet(self):
        try:
            with open(DARK_QSS_PATH, "r", encoding="utf-8") as f:
                qss = f.read()
            QApplication.instance().setStyleSheet(qss)
        except OSError:
            pass

    def _build_menu(self):
        menu_bar: QMenuBar = self.menuBar()
        help_menu = menu_bar.addMenu("帮助")

        about_action = QAction("关于 EasySay", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _build_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+Return"), self, self.generate_audio)
        QShortcut(QKeySequence("Ctrl+Enter"), self, self.generate_audio)
        QShortcut(QKeySequence("Ctrl+O"), self, self.select_folder)
        QShortcut(QKeySequence("Ctrl+P"), self, self.preview_audio)
        QShortcut(QKeySequence("Escape"), self, self._cancel_generation)

    def _show_about(self):
        AboutDialog(self).exec()

    def _build_ui(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 16, 20, 16)
        self.setCentralWidget(widget)

        layout.addWidget(self._build_voice_card())
        layout.addWidget(self._build_output_card())
        layout.addWidget(self._build_text_card(), stretch=1)
        layout.addWidget(self.copyright_label())

        self.lang_combo.currentTextChanged.connect(self.on_language_changed)
        self.gender_combo.currentTextChanged.connect(self.refresh_voice_list)
        self.voice_combo.currentTextChanged.connect(self.update_desc)
        self.text_input.textChanged.connect(self._on_text_changed)
        self.rate_edit.textChanged.connect(self._on_rate_text_changed)
        self.refresh_voice_list()

    # -- 卡片①：音色设置 --------------------------------------------------
    def _build_voice_card(self) -> QGroupBox:
        card = QGroupBox("① 音色设置")

        self.lang_combo = QComboBox()
        self.lang_combo.addItems([PLACEHOLDER] + self.voice_repo.language_options)

        self.gender_combo = QComboBox()
        self.gender_combo.addItems([PLACEHOLDER])
        self.gender_combo.setEnabled(False)

        self.voice_combo = QComboBox()
        self.voice_combo.addItems([PLACEHOLDER])
        self.voice_combo.setEnabled(False)

        self.rate_edit = QLineEdit("+0%")
        self.rate_edit.setObjectName("rateEdit")
        self.rate_edit.setFixedWidth(90)
        self.rate_edit.setToolTip("语速调整范围：-50% ~ +50%，例如 +10% 或 -20%")

        self.rate_error_label = QLabel()
        self.rate_error_label.setObjectName("errorLabel")
        self.rate_error_label.setVisible(False)

        self.btn_preview = QPushButton("试听")
        self.btn_preview.setObjectName("secondaryButton")
        self.btn_preview.clicked.connect(self.preview_audio)

        self.voice_desc_label = QLabel("【音色信息】请选择音色")
        self.voice_desc_label.setObjectName("voice_desc_label")

        # --- 第一行：语言 → 性别 → 音色 (三级联动) ---
        row1 = QHBoxLayout()
        row1.setSpacing(8)
        row1.addWidget(self._field_label("语言"))
        row1.addWidget(self.lang_combo)
        row1.addWidget(self._field_label("性别"))
        row1.addWidget(self.gender_combo)
        row1.addWidget(self._field_label("音色"))
        row1.addWidget(self.voice_combo, stretch=1)

        # --- 第二行：语速 / 音色描述 / 试听 ---
        row2 = QHBoxLayout()
        row2.setSpacing(8)
        row2.addWidget(self._field_label("语速"))
        row2.addWidget(self.rate_edit)
        row2.addWidget(self.rate_error_label)
        row2.addWidget(self.voice_desc_label, stretch=1)
        row2.addWidget(self.btn_preview)

        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(10)
        card_layout.addLayout(row1)
        card_layout.addLayout(row2)
        return card

    # -- 卡片②：输出设置 --------------------------------------------------
    def _build_output_card(self) -> QGroupBox:
        card = QGroupBox("② 输出设置")
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(10)

        dir_row = QHBoxLayout()
        dir_row.setSpacing(8)
        self.dir_edit = QLineEdit()
        self.dir_edit.setObjectName("dirEdit")
        self.dir_edit.setReadOnly(True)
        self.dir_edit.setPlaceholderText("尚未选择输出目录")
        btn_select_dir = QPushButton("选择目录")
        btn_select_dir.setObjectName("secondaryButton")
        btn_select_dir.clicked.connect(self.select_folder)
        dir_row.addWidget(self._field_label("输出目录"))
        dir_row.addWidget(self.dir_edit, stretch=1)
        dir_row.addWidget(btn_select_dir)

        fname_row = QHBoxLayout()
        fname_row.setSpacing(8)
        self.fname_edit = QLineEdit("audio")
        self.pause_combo = QComboBox()
        self.pause_combo.addItems(["无停顿"] + [f"{i}秒" for i in range(1, 7)])
        self.pause_combo.setFixedWidth(80)
        self.pause_combo.setToolTip("在句子标点处插入静音间隔，模拟自然语速节奏")
        fname_row.addWidget(self._field_label("文件名"))
        fname_row.addWidget(self.fname_edit, stretch=1)
        fname_row.addWidget(self._field_label("标点停顿"))
        fname_row.addWidget(self.pause_combo)

        self.dir_error_label = QLabel()
        self.dir_error_label.setObjectName("errorLabel")
        self.dir_error_label.setVisible(False)

        card_layout.addLayout(dir_row)
        card_layout.addLayout(fname_row)
        card_layout.addWidget(self.dir_error_label)
        return card

    # -- 卡片③：文本与生成 --------------------------------------------------
    def _build_text_card(self) -> QGroupBox:
        card = QGroupBox("③ 文本与生成")
        card.setObjectName("primaryCard")
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(10)

        self.text_input = QTextEdit()
        self.text_input.setPlaceholderText("粘贴文本（中文/英文/日语/韩语/法语/西语/意大利语）...")

        self.text_error_label = QLabel()
        self.text_error_label.setObjectName("errorLabel")
        self.text_error_label.setVisible(False)

        self.char_count_label = QLabel()
        self.char_count_label.setObjectName("charCountLabel")
        self.char_count_label.setAlignment(Qt.AlignRight)

        self.equalizer = EqualizerWidget()
        self.equalizer.setFixedHeight(40)

        self.status_label = QLabel("就绪")
        self.status_label.setObjectName("status_label")

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self.btn_generate = QPushButton("生成 MP3 (Ctrl+Enter)")
        self.btn_generate.setObjectName("generateButton")
        self.btn_generate.clicked.connect(self.generate_audio)

        self.btn_cancel = QPushButton("取消生成 (Esc)")
        self.btn_cancel.setObjectName("secondaryButton")
        self.btn_cancel.clicked.connect(self._cancel_generation)
        self.btn_cancel.setVisible(False)

        btn_row.addWidget(self.btn_generate, stretch=1)
        btn_row.addWidget(self.btn_cancel)

        self.voice_error_label = QLabel()
        self.voice_error_label.setObjectName("errorLabel")
        self.voice_error_label.setVisible(False)

        card_layout.addWidget(self.text_input, stretch=1)
        card_layout.addWidget(self.text_error_label)
        card_layout.addWidget(self.char_count_label)
        card_layout.addWidget(self.equalizer)
        card_layout.addWidget(self.status_label)
        card_layout.addWidget(self.voice_error_label)
        card_layout.addLayout(btn_row)
        return card

    @staticmethod
    def _field_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("fieldLabel")
        return label

    def copyright_label(self) -> QLabel:
        label = QLabel(
            "1. 本软件可免费自由传播使用　2. 未经授权严禁售卖，侵权行为我方将依法追究法律责任　"
            "作者：一直要求进步的昌强同学"
        )
        label.setObjectName("copyright_label")
        label.setAlignment(Qt.AlignCenter)
        return label

    def _restore_settings(self):
        if self.output_dir:
            self.dir_edit.setText(self.output_dir)

        last_lang = self.settings.get("last_lang")
        if last_lang and last_lang != PLACEHOLDER:
            idx = self.lang_combo.findText(last_lang)
            if idx >= 0:
                self.lang_combo.setCurrentIndex(idx)

        self.rate_edit.setText(self.settings.get("last_rate"))
        self.fname_edit.setText(self.settings.get("last_filename"))

        last_pause = self.settings.get("last_pause")
        if last_pause:
            idx = self.pause_combo.findText(last_pause)
            if idx >= 0:
                self.pause_combo.setCurrentIndex(idx)

    # ------------------------------------------------------------------
    # 字数统计 & 时长估算
    # ------------------------------------------------------------------
    def _on_text_changed(self):
        self._clear_errors()
        self._update_char_count()

    def _update_char_count(self):
        text = self.text_input.toPlainText()
        char_count = len(text.replace("\n", "").replace("\r", "").replace(" ", ""))
        if char_count == 0:
            self.char_count_label.setText("")
            return

        lang = self.lang_combo.currentText()
        cps = _CHAR_PER_SECOND.get(lang, _DEFAULT_CPS)
        estimated_sec = char_count / cps

        # 考虑语速调整
        rate_text = self.rate_edit.text()
        rate_match = _RATE_PATTERN.match(rate_text)
        if rate_match:
            rate_pct = int(rate_text.replace("%", "")) / 100.0
            estimated_sec = estimated_sec / (1 + rate_pct)

        # 考虑停顿
        pause_text = self.pause_combo.currentText()
        if pause_text != "无停顿":
            pause_sec = int(pause_text[0])
            # 粗略估算句子数：按标点切分
            sentence_count = len(re.findall(r'[。！？.!?]', text)) or 1
            estimated_sec += sentence_count * pause_sec

        minutes = int(estimated_sec // 60)
        seconds = int(estimated_sec % 60)
        if minutes > 0:
            duration_str = f"{minutes}分{seconds}秒"
        else:
            duration_str = f"{seconds}秒"

        self.char_count_label.setText(f"有效字符：{char_count} 字  |  预计时长：约 {duration_str}")

    # ------------------------------------------------------------------
    # 语速校验
    # ------------------------------------------------------------------
    def _on_rate_text_changed(self):
        text = self.rate_edit.text()
        if not text:
            return
        if _RATE_PATTERN.match(text):
            val = int(text.replace("%", ""))
            if -50 <= val <= 50:
                self.rate_error_label.setVisible(False)
                self._update_char_count()
                return
        self.rate_error_label.setText("⚠ 请输入 -50% ~ +50%")
        self.rate_error_label.setVisible(True)

    # ------------------------------------------------------------------
    # 联动逻辑
    # ------------------------------------------------------------------
    def on_language_changed(self):
        self.gender_combo.clear()
        self.gender_combo.addItems([PLACEHOLDER, "Male", "Female"])
        self.gender_combo.setEnabled(self.lang_combo.currentText() != PLACEHOLDER)

        self.voice_combo.clear()
        self.voice_combo.addItems([PLACEHOLDER])
        self.voice_combo.setEnabled(False)
        self.update_desc("")
        self._update_char_count()

    def refresh_voice_list(self):
        lang_sel = self.lang_combo.currentText()
        gender_sel = self.gender_combo.currentText()
        self.voice_combo.clear()
        self.voice_combo.addItems([PLACEHOLDER])

        if lang_sel == PLACEHOLDER or gender_sel == PLACEHOLDER:
            self.voice_combo.setEnabled(False)
            self.update_desc("")

        candidates = self.voice_repo.filter_by(lang_sel, gender_sel)
        self.voice_combo.addItems(candidates)
        self.voice_combo.setEnabled(True)
        self.update_desc(self.voice_combo.currentText())

    def update_desc(self, voice_name: str):
        self.voice_desc_label.setText(self.voice_repo.describe(voice_name))

    def select_folder(self):
        path = QFileDialog.getExistingDirectory(self, "选择文件夹")
        if path:
            self.output_dir = path
            self.dir_edit.setText(path)

    # ------------------------------------------------------------------
    # 试听
    # ------------------------------------------------------------------
    def _parse_pause_seconds(self) -> int:
        text = self.pause_combo.currentText()
        if text == "无停顿":
            return 0
        return int(text[0])

    def preview_audio(self):
        lang = self.lang_combo.currentText()
        voice = self.voice_combo.currentText()
        if lang == PLACEHOLDER:
            self._show_error(self.voice_error_label, "请先选择语言")
            return
        if voice == PLACEHOLDER:
            self._show_error(self.voice_error_label, "请先筛选并选择音色")
            return

        preview_text = _PREVIEW_TEXTS.get(lang, _PREVIEW_TEXTS["中文 (zh)"])
        rate = self.rate_edit.text()

        self.btn_preview.setEnabled(False)
        self.btn_preview.setText("试听中...")
        self._preview_tmp = None

        self.preview_worker = PreviewWorker(preview_text, voice, rate)
        self.preview_worker.finished_signal.connect(self._on_preview_complete)
        self.preview_worker.start()

    def _on_preview_complete(self, success: bool, msg: str):
        self.btn_preview.setEnabled(True)
        self.btn_preview.setText("试听")
        if success:
            self._preview_tmp = msg
            self._media_player.setSource(QUrl.fromLocalFile(msg))
            self._media_player.play()
        else:
            QMessageBox.critical(self, "试听失败", f"生成试听音频失败：{msg}")

    def closeEvent(self, event):
        self._persist_settings()
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait(3000)
        if self._preview_tmp and os.path.exists(self._preview_tmp):
            try:
                os.remove(self._preview_tmp)
            except OSError:
                pass
        super().closeEvent(event)

    def _clear_errors(self):
        self.text_error_label.setVisible(False)
        self.dir_error_label.setVisible(False)
        self.voice_error_label.setVisible(False)

    def _show_error(self, label: QLabel, msg: str):
        label.setText("⚠ " + msg)
        label.setVisible(True)

    # ------------------------------------------------------------------
    # 生成流程
    # ------------------------------------------------------------------
    def generate_audio(self):
        self._clear_errors()

        text = self.text_input.toPlainText().strip()
        voice = self.voice_combo.currentText()
        lang_selected = self.lang_combo.currentText()

        if not text:
            self._show_error(self.text_error_label, "请输入文本")
            self.text_input.setFocus()
            return
        if not self.output_dir:
            self._show_error(self.dir_error_label, "请选择输出目录")
            return
        if voice == PLACEHOLDER:
            self._show_error(self.voice_error_label, "请筛选并选择音色")
            return

        # 语速校验
        rate = self.rate_edit.text().strip()
        if not _RATE_PATTERN.match(rate):
            self._show_error(self.voice_error_label, "语速格式错误，请输入如 +10% 或 -20%")
            return
        rate_val = int(rate.replace("%", ""))
        if rate_val < -50 or rate_val > 50:
            self._show_error(self.voice_error_label, "语速范围仅支持 -50% ~ +50%")
            return

        errors = validate_text_language(text, lang_selected)
        if errors:
            self._show_error(self.text_error_label, format_errors(errors, lang_selected))
            return

        fname = self.fname_edit.text().strip() or "audio"
        if not fname.lower().endswith(".mp3"):
            fname += ".mp3"
        full_path = os.path.join(self.output_dir, fname)

        # 文件覆盖确认
        if os.path.exists(full_path):
            reply = QMessageBox.question(
                self, "文件已存在",
                f"「{fname}」已存在，是否覆盖？\n\n{full_path}",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return

        pause_seconds = self._parse_pause_seconds()
        self._last_generated_path = full_path
        self._set_generating_state(True)

        self.worker = TTSWorker(text, voice, rate, full_path, pause_seconds)
        self.worker.progress_signal.connect(self._on_progress)
        self.worker.finished_signal.connect(self.on_complete)
        self.worker.start()

        self._persist_settings()

    def _cancel_generation(self):
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.status_label.setText("正在取消...")

    def _set_generating_state(self, generating: bool):
        if generating:
            self.status_label.setText("正在生成音频...")
            self.btn_generate.setVisible(False)
            self.btn_cancel.setVisible(True)
            self.equalizer.start()
        else:
            self.status_label.setText("就绪")
            self.btn_generate.setVisible(True)
            self.btn_cancel.setVisible(False)
            self.equalizer.stop()

    def _on_progress(self, percent: int):
        self.status_label.setText(f"正在生成音频...{percent}%")

    def on_complete(self, success: bool, msg: str):
        self._set_generating_state(False)
        if success:
            self.status_label.setText(f"已完成：{msg}")
            reply = QMessageBox.information(
                self, "生成完成", msg,
                QMessageBox.Ok | QMessageBox.Open,
                QMessageBox.Ok,
            )
            if reply == QMessageBox.Open:
                self._open_folder(self._last_generated_path)
        else:
            self.status_label.setText(f"生成失败：{msg}")
            if "已取消" not in msg:
                QMessageBox.critical(self, "错误", msg)

    def _open_folder(self, file_path: str):
        """在文件管理器中打开并选中生成的文件"""
        folder = os.path.dirname(file_path)
        if not os.path.exists(file_path):
            return
        if platform.system() == "Windows":
            subprocess.run(["explorer", "/select,", file_path])
        elif platform.system() == "Darwin":
            subprocess.run(["open", "-R", file_path])
        else:
            subprocess.run(["xdg-open", folder])

    def _persist_settings(self):
        self.settings.set("last_output_dir", self.output_dir)
        self.settings.set("last_lang", self.lang_combo.currentText())
        self.settings.set("last_rate", self.rate_edit.text())
        self.settings.set("last_filename", self.fname_edit.text().strip())
        self.settings.set("last_pause", self.pause_combo.currentText())
        self.settings.save()
