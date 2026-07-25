"""EasySay 主窗口"""
import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QAction
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QLineEdit, QPushButton, QComboBox, QLabel, QFileDialog,
    QMessageBox, QGroupBox, QMenuBar,
)

from app.config import APP_DISPLAY_NAME, APP_ICON_PATH, DARK_QSS_PATH
from app.core.settings_manager import SettingsManager
from app.core.tts_worker import TTSWorker
from app.core.validator import validate_text_language, format_errors
from app.core.voice_repository import VoiceRepository
from app.ui.about_dialog import AboutDialog
from app.ui.equalizer_widget import EqualizerWidget

PLACEHOLDER = "请选择"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_DISPLAY_NAME)
        self.setWindowIcon(QIcon(APP_ICON_PATH))
        self.resize(1280, 960)

        self.voice_repo = VoiceRepository()
        self.settings = SettingsManager()
        self.output_dir = self.settings.get("last_output_dir") or ""
        self.worker: TTSWorker | None = None

        self._load_stylesheet()
        self._build_menu()
        self._build_ui()
        self._restore_settings()

    # ------------------------------------------------------------------
    # 初始化 UI
    # ------------------------------------------------------------------
    def _load_stylesheet(self):
        try:
            with open(DARK_QSS_PATH, "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())
        except OSError:
            pass  # 样式文件缺失不影响功能运行

    def _build_menu(self):
        menu_bar: QMenuBar = self.menuBar()
        help_menu = menu_bar.addMenu("帮助")

        about_action = QAction("关于 EasySay", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

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

        self.refresh_voice_list()

    # -- 卡片①：音色设置 --------------------------------------------------
    def _build_voice_card(self) -> QGroupBox:
        card = QGroupBox("① 音色设置")
        row = QHBoxLayout()
        row.setSpacing(8)

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
        self.rate_edit.setFixedWidth(110)

        row.addWidget(self._field_label("语言"))
        row.addWidget(self.lang_combo)
        row.addWidget(self._field_label("性别"))
        row.addWidget(self.gender_combo)
        row.addWidget(self._field_label("音色"))
        row.addWidget(self.voice_combo, stretch=1)
        row.addWidget(self._field_label("语速"))
        row.addWidget(self.rate_edit)

        self.voice_desc_label = QLabel("【音色信息】请选择音色")
        self.voice_desc_label.setObjectName("voice_desc_label")

        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(10)
        card_layout.addLayout(row)
        card_layout.addWidget(self.voice_desc_label)
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
        fname_row.addWidget(self._field_label("文件名"))
        fname_row.addWidget(self.fname_edit, stretch=1)

        card_layout.addLayout(dir_row)
        card_layout.addLayout(fname_row)
        return card

    # -- 卡片③：文本与生成 ------------------------------------------------
    def _build_text_card(self) -> QGroupBox:
        card = QGroupBox("③ 文本与生成")
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(10)

        self.text_input = QTextEdit()
        self.text_input.setPlaceholderText("粘贴文本（中文/英文/日语/韩语/法语/西语/意大利语）...")

        status_row = QHBoxLayout()
        status_row.setSpacing(10)
        self.equalizer = EqualizerWidget()
        self.status_label = QLabel("就绪")
        self.status_label.setObjectName("status_label")
        status_row.addWidget(self.equalizer)
        status_row.addWidget(self.status_label, stretch=1)

        btn_gen = QPushButton("生成 MP3")
        btn_gen.setObjectName("generateButton")
        btn_gen.clicked.connect(self.generate_audio)

        card_layout.addWidget(self.text_input, stretch=1)
        card_layout.addLayout(status_row)
        card_layout.addWidget(btn_gen)
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
        """启动时恢复上次的输出目录 / 语言 / 语速 / 文件名"""
        if self.output_dir:
            self.dir_edit.setText(self.output_dir)

        last_lang = self.settings.get("last_lang")
        if last_lang and last_lang != PLACEHOLDER:
            idx = self.lang_combo.findText(last_lang)
            if idx >= 0:
                self.lang_combo.setCurrentIndex(idx)

        self.rate_edit.setText(self.settings.get("last_rate"))
        self.fname_edit.setText(self.settings.get("last_filename"))

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

    def refresh_voice_list(self):
        lang_sel = self.lang_combo.currentText()
        gender_sel = self.gender_combo.currentText()
        self.voice_combo.clear()
        self.voice_combo.addItems([PLACEHOLDER])

        if lang_sel == PLACEHOLDER or gender_sel == PLACEHOLDER:
            self.voice_combo.setEnabled(False)
            self.update_desc("")
            return

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
    # 生成流程
    # ------------------------------------------------------------------
    def generate_audio(self):
        text = self.text_input.toPlainText().strip()
        voice = self.voice_combo.currentText()
        lang_selected = self.lang_combo.currentText()

        if not text:
            QMessageBox.warning(self, "提示", "请输入文本")
            return
        if not self.output_dir:
            QMessageBox.warning(self, "提示", "请选择文件目录")
            return
        if voice == PLACEHOLDER:
            QMessageBox.warning(self, "提示", "请筛选并选择音色！")
            return

        errors = validate_text_language(text, lang_selected)
        if errors:
            QMessageBox.warning(self, "文本语言校验失败", format_errors(errors, lang_selected))
            return

        fname = self.fname_edit.text().strip() or "audio"
        if not fname.lower().endswith(".mp3"):
            fname += ".mp3"
        full_path = os.path.join(self.output_dir, fname)

        rate = self.rate_edit.text()
        self._set_generating_state(True)

        self.worker = TTSWorker(text, voice, rate, full_path)
        self.worker.progress_signal.connect(self._on_progress)
        self.worker.finished_signal.connect(self.on_complete)
        self.worker.start()

        self._persist_settings()

    def _set_generating_state(self, generating: bool):
        self.status_label.setText("正在生成音频..." if generating else "就绪")
        if generating:
            self.equalizer.start()
        else:
            self.equalizer.stop()

    def _on_progress(self, percent: int):
        self.status_label.setText(f"正在生成音频...{percent}%")

    def on_complete(self, success: bool, msg: str):
        self.equalizer.stop()
        if success:
            self.status_label.setText("已完成：" + msg)
            QMessageBox.information(self, "完成", msg)
        else:
            self.status_label.setText("生成失败：" + msg)
            QMessageBox.critical(self, "错误", msg)

    def _persist_settings(self):
        self.settings.set("last_output_dir", self.output_dir)
        self.settings.set("last_lang", self.lang_combo.currentText())
        self.settings.set("last_rate", self.rate_edit.text())
        self.settings.set("last_filename", self.fname_edit.text().strip())
        self.settings.save()

    def closeEvent(self, event):
        self._persist_settings()
        super().closeEvent(event)
