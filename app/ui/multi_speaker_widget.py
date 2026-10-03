"""多人对话模式 Widget

左栏维护多个「说话人」（角色名 + 语言 + 性别 + 音色 + 试听），
右栏用「角色名：台词」纯文本脚本编写对话，生成时逐行按对应音色合成，
拼接为单个 MP3。
"""
import os
import platform
import re
import subprocess

from PySide6.QtCore import Qt, QUrl, QEvent
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QLineEdit,
    QComboBox, QPushButton, QTextEdit, QScrollArea, QFileDialog,
    QMessageBox, QSplitter,
)
from PySide6.QtMultimedia import QMediaPlayer

from app.core.settings_manager import SettingsManager
from app.core.tts_preview_worker import PreviewWorker
from app.core.multi_speaker_worker import MultiSpeakerWorker
from app.core.validator import validate_text_language, format_errors
from app.core.voice_repository import VoiceRepository
from app.ui.equalizer_widget import EqualizerWidget
from app.ui.line_number_edit import LineNumberTextEdit

PLACEHOLDER = "请选择"

# 说话人角色色板（与主题琥珀色区分，仅用于身份标识）
SPEAKER_COLORS = [
    "#5B8DEF", "#C77DFF", "#F472B6", "#FBBF24", "#34D399",
    "#60A5FA", "#F87171", "#2DD4BF", "#A3E635", "#FB923C",
]

# 各语种试听文本
_PREVIEW_TEXTS = {
    "中文 (zh)": "你好，我是一直要求进步的昌强同学。",
    "英语 (en)": "Hello, I'm Changqiang, always striving to improve.",
    "日语 (ja)": "こんにちは、私はいつも進歩を求める昌強です。",
    "韩语 (ko)": "안녕하세요, 저는 항상 진보를 추구하는 창창입니다.",
    "法语 (fr)": "Bonjour, je suis Changqiang, toujours en quête de progrès.",
    "意大利语 (it)": "Ciao, sono Changqiang, sempre alla ricerca del progresso.",
    "西班牙语 (es)": "Hola, soy Changqiang, siempre buscando progresar.",
}

_RATE_PATTERN = re.compile(r'^[+-]\d{1,2}%$')
# 台词行格式：角色名：台词 或 角色名:台词
_LINE_PATTERN = re.compile(r'^([^：:]+)[：:]\s*(.*)$')


class _SpeakerCard(QGroupBox):
    """单个说话人配置卡片：角色名 + 语言 + 性别 + 音色 + 试听 + 删除"""

    def __init__(self, repo: VoiceRepository, media_player: QMediaPlayer,
                 name: str, color: str, parent=None):
        super().__init__(parent)
        self._repo = repo
        self._media_player = media_player
        self._color = color
        self._preview_worker: PreviewWorker | None = None
        self._on_change = lambda: None
        self._on_remove = lambda _card: None

        self.setProperty("speakerCard", True)
        self.setStyleSheet(
            f"QGroupBox {{ border-left: 3px solid {color}; }}"
        )

        self.name_edit = QLineEdit(name)
        self.name_edit.setObjectName("speakerNameEdit")
        self.name_edit.setPlaceholderText("角色名（脚本中引用）")

        self.lang_combo = QComboBox()
        self.lang_combo.addItems([PLACEHOLDER] + repo.language_options)

        self.gender_combo = QComboBox()
        self.gender_combo.addItems([PLACEHOLDER, "男", "女"])
        self.gender_combo.setEnabled(False)

        self.voice_combo = QComboBox()
        self.voice_combo.addItems([PLACEHOLDER])
        self.voice_combo.setEnabled(False)

        self.btn_preview = QPushButton("试听")
        self.btn_preview.setObjectName("secondaryButton")
        self.btn_preview.setEnabled(False)
        self.btn_preview.clicked.connect(self._preview)

        self.btn_remove = QPushButton("✕")
        self.btn_remove.setObjectName("removeSpeakerButton")
        self.btn_remove.setFixedWidth(28)
        self.btn_remove.setToolTip("删除该说话人")
        self.btn_remove.clicked.connect(self._emit_remove)

        row1 = QHBoxLayout()
        row1.setSpacing(6)
        row1.addWidget(self.name_edit, stretch=1)
        row1.addWidget(self.btn_remove)

        grid = QVBoxLayout()
        grid.setSpacing(6)

        r_lang = QHBoxLayout()
        r_lang.addWidget(QLabel("语言"))
        r_lang.addWidget(self.lang_combo, stretch=1)
        grid.addLayout(r_lang)

        r_gender = QHBoxLayout()
        r_gender.addWidget(QLabel("性别"))
        r_gender.addWidget(self.gender_combo, stretch=1)
        grid.addLayout(r_gender)

        r_voice = QHBoxLayout()
        r_voice.addWidget(QLabel("音色"))
        r_voice.addWidget(self.voice_combo, stretch=1)
        r_voice.addWidget(self.btn_preview)
        grid.addLayout(r_voice)

        layout = QVBoxLayout(self)
        layout.setSpacing(6)
        layout.addLayout(row1)
        layout.addLayout(grid)

        self.lang_combo.currentTextChanged.connect(self._on_lang_changed)
        self.gender_combo.currentTextChanged.connect(self._refresh_voices)
        self.voice_combo.currentTextChanged.connect(self._on_voice_changed)

    # -- 对外信号转发（用回调，避免内嵌类信号复杂度） --
    def set_callbacks(self, on_change, on_remove):
        self._on_change = on_change
        self._on_remove = on_remove
        self.name_edit.textChanged.connect(lambda _: self._on_change())

    def _emit_remove(self):
        self._on_remove(self)

    # -- 联动逻辑 --
    def _on_lang_changed(self):
        self.gender_combo.clear()
        self.gender_combo.addItems([PLACEHOLDER, "男", "女"])
        self.gender_combo.setEnabled(self.lang_combo.currentText() != PLACEHOLDER)
        self.voice_combo.clear()
        self.voice_combo.addItems([PLACEHOLDER])
        self.voice_combo.setEnabled(False)
        self.btn_preview.setEnabled(False)
        self._on_change()

    def _refresh_voices(self):
        lang = self.lang_combo.currentText()
        gender_zh = self.gender_combo.currentText()
        self.voice_combo.clear()
        self.voice_combo.addItems([PLACEHOLDER])

        if lang == PLACEHOLDER or gender_zh == PLACEHOLDER:
            self.voice_combo.setEnabled(False)
            self.btn_preview.setEnabled(False)
            self._on_change()
            return

        gender = "Male" if gender_zh == "男" else "Female"
        candidates = self._repo.filter_by(lang, gender)
        for c in candidates:
            self.voice_combo.addItem(self._repo.localized_name(c), c)
        self.voice_combo.setEnabled(True)
        self._on_change()

    def _on_voice_changed(self):
        self.btn_preview.setEnabled(self._get_voice() != PLACEHOLDER)
        self._on_change()

    # -- 查询 --
    def _get_voice(self) -> str:
        idx = self.voice_combo.currentIndex()
        if idx <= 0:
            return self.voice_combo.currentText()
        original = self.voice_combo.itemData(idx)
        return original if original else self.voice_combo.currentText()

    def config(self) -> dict:
        return {
            "name": self.name_edit.text().strip(),
            "lang": self.lang_combo.currentText(),
            "gender": self.gender_combo.currentText(),
            "voice": self._get_voice(),
        }

    def is_complete(self) -> bool:
        c = self.config()
        return bool(c["name"]) and c["lang"] != PLACEHOLDER \
            and c["gender"] != PLACEHOLDER and c["voice"] != PLACEHOLDER

    # -- 试听 --
    def _preview(self):
        lang = self.lang_combo.currentText()
        voice = self._get_voice()
        if lang == PLACEHOLDER or voice == PLACEHOLDER:
            return
        self.btn_preview.setEnabled(False)
        self.btn_preview.setText("试听中...")
        self._preview_worker = PreviewWorker(
            _PREVIEW_TEXTS.get(lang, _PREVIEW_TEXTS["中文 (zh)"]), voice, "-10%"
        )
        self._preview_worker.finished_signal.connect(self._on_preview_done)
        self._preview_worker.start()

    def _on_preview_done(self, success: bool, msg: str):
        self.btn_preview.setEnabled(True)
        self.btn_preview.setText("试听")
        if success:
            self._media_player.setSource(QUrl.fromLocalFile(msg))
            self._media_player.play()

    def abort(self):
        if self._preview_worker and self._preview_worker.isRunning():
            self._preview_worker.terminate()


class MultiSpeakerWidget(QWidget):
    def __init__(self, media_player: QMediaPlayer, parent=None):
        super().__init__(parent)
        self._media_player = media_player
        self._repo = VoiceRepository()
        self.settings = getattr(parent, "settings", None) or SettingsManager()

        self._cards: list[_SpeakerCard] = []
        self._worker: MultiSpeakerWorker | None = None
        self._last_generated_path: str | None = None

        self._build_ui()
        # 初始两个说话人
        self._add_speaker("角色A")
        self._add_speaker("角色B")

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 4, 0, 0)
        root.setSpacing(10)

        splitter = QSplitter(Qt.Horizontal)

        # --- 左栏：说话人面板 ---
        self.speaker_scroll = QScrollArea()
        self.speaker_scroll.setWidgetResizable(True)
        self.speaker_scroll.setMinimumWidth(280)
        self.speaker_scroll.setMaximumWidth(360)

        speaker_host = QWidget()
        self.speaker_layout = QVBoxLayout(speaker_host)
        self.speaker_layout.setContentsMargins(0, 0, 6, 0)
        self.speaker_layout.setSpacing(10)
        self.speaker_layout.addStretch()

        self.btn_add_speaker = QPushButton("＋ 添加说话人")
        self.btn_add_speaker.setObjectName("secondaryButton")
        self.btn_add_speaker.clicked.connect(self._on_add_speaker)
        self.speaker_layout.addWidget(self.btn_add_speaker)

        self.speaker_scroll.setWidget(speaker_host)
        splitter.addWidget(self.speaker_scroll)

        # --- 右栏：脚本 + 输出 + 生成 ---
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(6, 0, 0, 0)
        right_layout.setSpacing(10)

        right_layout.addWidget(self._build_script_card(), stretch=1)
        right_layout.addWidget(self._build_output_card())
        right_layout.addLayout(self._build_generate_row())

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        root.addWidget(splitter)

    def _build_script_card(self) -> QGroupBox:
        card = QGroupBox("对话脚本")
        card.setObjectName("primaryCard")
        layout = QVBoxLayout(card)
        layout.setSpacing(8)

        hint = QLabel("每行一条台词，格式：角色名：台词 或 角色名:台词")
        hint.setObjectName("charCountLabel")

        self.script_edit = LineNumberTextEdit()
        self.script_edit.setObjectName("dialogueScriptEdit")
        self.script_edit.setPlaceholderText(
            "\n Johnny: Hi everyone, welcome!\n Crystal: Hi Johnny, oh my god! You're my dream guy!\n Tina: Hi Johnny,oh my god! You’re my crush."
        )
        self.script_edit.textChanged.connect(self._on_script_changed)
        self.script_edit.installEventFilter(self)

        self.parse_label = QLabel("共 0 句台词")
        self.parse_label.setObjectName("charCountLabel")

        self.error_label = QLabel()
        self.error_label.setObjectName("errorLabel")
        self.error_label.setVisible(False)

        layout.addWidget(hint)
        layout.addWidget(self.script_edit, stretch=1)
        layout.addWidget(self.parse_label)
        layout.addWidget(self.error_label)
        return card

    def _build_output_card(self) -> QGroupBox:
        card = QGroupBox("输出设置")
        layout = QVBoxLayout(card)
        layout.setSpacing(8)

        dir_row = QHBoxLayout()
        self.dir_edit = QLineEdit()
        self.dir_edit.setObjectName("dirEdit")
        self.dir_edit.setReadOnly(True)
        self.dir_edit.setPlaceholderText("尚未选择输出目录")
        saved_dir = self.settings.get("last_output_dir") or ""
        if saved_dir:
            self.dir_edit.setText(saved_dir)
        btn_dir = QPushButton("选择目录")
        btn_dir.setObjectName("secondaryButton")
        btn_dir.clicked.connect(self._select_dir)
        dir_row.addWidget(QLabel("输出目录"))
        dir_row.addWidget(self.dir_edit, stretch=1)
        dir_row.addWidget(btn_dir)
        layout.addLayout(dir_row)

        fname_row = QHBoxLayout()
        self.fname_edit = QLineEdit("dialogue")
        self.rate_edit = QLineEdit("-10%")
        self.rate_edit.setObjectName("rateEdit")
        self.rate_edit.setFixedWidth(80)
        self.pause_combo = QComboBox()
        self.pause_combo.addItems(["无停顿"] + [f"{i}秒" for i in range(1, 7)])
        self.pause_combo.setFixedWidth(80)
        fname_row.addWidget(QLabel("文件名"))
        fname_row.addWidget(self.fname_edit, stretch=1)
        fname_row.addWidget(QLabel("语速"))
        fname_row.addWidget(self.rate_edit)
        fname_row.addWidget(QLabel("行间停顿"))
        fname_row.addWidget(self.pause_combo)
        layout.addLayout(fname_row)
        return card

    def _build_generate_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)

        self.equalizer = EqualizerWidget()
        self.equalizer.setFixedHeight(40)

        self.status_label = QLabel("就绪")
        self.status_label.setObjectName("status_label")

        self.btn_generate = QPushButton("生成对话 MP3 (Ctrl+Enter)")
        self.btn_generate.setObjectName("generateButton")
        self.btn_generate.clicked.connect(self.generate)

        self.btn_cancel = QPushButton("取消生成 (Esc)")
        self.btn_cancel.setObjectName("secondaryButton")
        self.btn_cancel.setVisible(False)
        self.btn_cancel.clicked.connect(self._cancel)

        row.addWidget(self.equalizer)
        row.addWidget(self.status_label, stretch=1)
        row.addWidget(self.btn_generate)
        row.addWidget(self.btn_cancel)
        return row

    # ------------------------------------------------------------------
    # 说话人管理
    # ------------------------------------------------------------------
    def _add_speaker(self, name: str = ""):
        idx = len(self._cards)
        color = SPEAKER_COLORS[idx % len(SPEAKER_COLORS)]
        if not name:
            name = f"角色{chr(ord('A') + idx)}" if idx < 26 else f"角色{idx + 1}"
        card = _SpeakerCard(self._repo, self._media_player, name, color, self)
        card.set_callbacks(self._refresh_parse_label, self._remove_speaker)
        # 插入到 stretch 之前
        self.speaker_layout.insertWidget(self.speaker_layout.count() - 1, card)
        self._cards.append(card)
        self._refresh_parse_label()

    def _on_add_speaker(self):
        if len(self._cards) >= 10:
            QMessageBox.information(self, "提示", "最多支持 10 个说话人")
            return
        self._add_speaker("")

    def _remove_speaker(self, card: _SpeakerCard, silent: bool = False):
        min_count = 1 if silent else 2
        if len(self._cards) <= min_count:
            if not silent:
                QMessageBox.information(self, "提示", "至少需要保留 2 个说话人")
            return
        card.abort()
        self.speaker_layout.removeWidget(card)
        card.deleteLater()
        self._cards.remove(card)
        self._refresh_parse_label()

    def _speaker_by_name(self, name: str):
        for c in self._cards:
            if c.config()["name"] == name:
                return c
        return None

    # ------------------------------------------------------------------
    # 脚本解析
    # ------------------------------------------------------------------
    def _parse_script(self) -> list[tuple[str, str]]:
        """返回 [(角色名, 台词)]，忽略空行与不含冒号的行"""
        result: list[tuple[str, str]] = []
        for raw_line in self.script_edit.toPlainText().splitlines():
            line = raw_line.strip()
            if not line:
                continue
            m = _LINE_PATTERN.match(line)
            if not m:
                continue
            speaker, text = m.group(1).strip(), m.group(2).strip()
            if speaker and text:
                result.append((speaker, text))
        return result

    def _on_script_changed(self):
        self.error_label.setVisible(False)
        self._clean_script()
        self._refresh_parse_label()

    def _clean_script(self):
        """自动删除无用的空行：压缩连续空行、删除纯空白行，保留单个空行分隔"""
        text = self.script_edit.toPlainText()
        cleaned = re.sub(r'\n{3,}', '\n\n', text)
        cleaned = re.sub(r'\n[ \t]+\n', '\n', cleaned)
        if cleaned != text:
            cursor = self.script_edit.textCursor()
            pos = cursor.position()
            self.script_edit.blockSignals(True)
            self.script_edit.setPlainText(cleaned)
            cursor.setPosition(min(pos, len(cleaned)))
            self.script_edit.setTextCursor(cursor)
            self.script_edit.blockSignals(False)

    def eventFilter(self, obj, event):
        if obj is self.script_edit and event.type() == QEvent.Type.FocusOut:
            self._sync_speakers_with_script()
        return super().eventFilter(obj, event)

    def _sync_speakers_with_script(self):
        """脚本失焦时，让左侧说话人与脚本保持一致：
        缺失的角色补卡，脚本中未再引用的角色自动删除（至少保留 1 人）。"""
        lines = self._parse_script()
        referenced = {s for s, _ in lines}

        # 1) 为脚本中出现但尚未配置的角色补卡
        existing = {c.config()["name"] for c in self._cards if c.config()["name"]}
        for speaker, _ in lines:
            if speaker in existing:
                continue
            if len(self._cards) >= 10:
                break
            self._add_speaker(speaker)
            existing.add(speaker)

        # 2) 删除脚本中未引用的角色（静默，至少保留 1 人）
        for card in list(self._cards):
            if len(self._cards) <= 1:
                break
            if card.config()["name"] not in referenced:
                self._remove_speaker(card, silent=True)

        self._refresh_parse_label()

    def _refresh_parse_label(self):
        lines = self._parse_script()
        names = {c.config()["name"] for c in self._cards if c.config()["name"]}
        unknown = [s for s, _ in lines if s not in names]
        text = f"共 {len(lines)} 句台词"
        if unknown:
            text += f"  |  未识别说话人：{'、'.join(dict.fromkeys(unknown))}"
        self.parse_label.setText(text)

    # ------------------------------------------------------------------
    # 目录
    # ------------------------------------------------------------------
    def _select_dir(self):
        path = QFileDialog.getExistingDirectory(self, "选择文件夹")
        if path:
            self.dir_edit.setText(path)

    # ------------------------------------------------------------------
    # 生成
    # ------------------------------------------------------------------
    def generate(self):
        self.error_label.setVisible(False)
        lines = self._parse_script()
        out_dir = self.dir_edit.text().strip()
        rate = self.rate_edit.text().strip()

        if not lines:
            self._show_error("脚本为空或格式不正确，请按「角色名：台词」逐行输入")
            return
        if not out_dir:
            self._show_error("请选择输出目录")
            return
        if not _RATE_PATTERN.match(rate):
            self._show_error("语速格式错误，请输入如 +10% 或 -20%")
            return

        # 逐行校验
        errors: list[str] = []
        for i, (speaker, text) in enumerate(lines, start=1):
            card = self._speaker_by_name(speaker)
            if card is None:
                errors.append(f"第{i}行：说话人「{speaker}」未在左侧配置")
                continue
            if not card.is_complete():
                errors.append(f"第{i}行：说话人「{speaker}」未选择完整音色")
                continue
            lang = card.config()["lang"]
            errs = validate_text_language(text, lang)
            if errs:
                errors.append(f"第{i}行（{speaker}）：" + format_errors(errs, lang))

        if errors:
            self._show_error("\n".join(errors[:8]))
            return

        fname = self.fname_edit.text().strip() or "dialogue"
        if not fname.lower().endswith(".mp3"):
            fname += ".mp3"
        full_path = os.path.join(out_dir, fname)

        if os.path.exists(full_path):
            reply = QMessageBox.question(
                self, "文件已存在",
                f"「{fname}」已存在，是否覆盖？\n\n{full_path}",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return

        payload = [
            {
                "speaker": speaker,
                "text": text,
                "voice": self._speaker_by_name(speaker).config()["voice"],
                "rate": rate,
            }
            for speaker, text in lines
        ]
        pause_seconds = self._parse_pause_seconds()

        self._last_generated_path = full_path
        self._set_generating(True)

        self._worker = MultiSpeakerWorker(payload, full_path, pause_seconds)
        self._worker.progress_signal.connect(self._on_progress)
        self._worker.finished_signal.connect(self._on_complete)
        self._worker.start()

        self.settings.set("last_output_dir", out_dir)
        self.settings.save()

    def _parse_pause_seconds(self) -> int:
        t = self.pause_combo.currentText()
        return 0 if t == "无停顿" else int(t[0])

    def _cancel(self):
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self.status_label.setText("正在取消...")

    def _set_generating(self, generating: bool):
        if generating:
            self.status_label.setText("正在生成对话...")
            self.btn_generate.setVisible(False)
            self.btn_cancel.setVisible(True)
            self.equalizer.start()
        else:
            self.status_label.setText("就绪")
            self.btn_generate.setVisible(True)
            self.btn_cancel.setVisible(False)
            self.equalizer.stop()

    def _on_progress(self, percent: int):
        self.status_label.setText(
            f'正在生成对话...<span style="color:#E8A33D; font-weight:600;">{percent}%</span>'
        )

    def _on_complete(self, success: bool, msg: str):
        self._set_generating(False)
        if success:
            self.status_label.setText(f"已完成：{msg}")
            reply = QMessageBox.information(
                self, "生成完成", msg,
                QMessageBox.Ok | QMessageBox.Open, QMessageBox.Ok,
            )
            if reply == QMessageBox.Open:
                self._open_folder(self._last_generated_path)
        else:
            self.status_label.setText(f"生成失败：{msg}")
            if "已取消" not in msg:
                QMessageBox.critical(self, "错误", msg)

    def _open_folder(self, file_path: str):
        folder = os.path.dirname(file_path)
        if not os.path.exists(file_path):
            return
        if platform.system() == "Windows":
            subprocess.run(["explorer", "/select,", file_path])
        elif platform.system() == "Darwin":
            subprocess.run(["open", "-R", file_path])
        else:
            subprocess.run(["xdg-open", folder])

    # ------------------------------------------------------------------
    # 工具
    # ------------------------------------------------------------------
    def _show_error(self, msg: str):
        self.error_label.setText("⚠ " + msg)
        self.error_label.setVisible(True)

    def abort_flow(self):
        for c in self._cards:
            c.abort()
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait(3000)
        self._media_player.stop()
        self._set_generating(False)
