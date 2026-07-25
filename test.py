import asyncio
import os
import re
import edge_tts
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                               QTextEdit, QLineEdit, QPushButton, QComboBox, QLabel, QFileDialog,
                               QMessageBox, QProgressBar)
from PySide6.QtCore import Qt, QThread, Signal


class TTSWorker(QThread):
    finished_signal = Signal(str)

    def __init__(self, text, voice, rate, save_path):
        super().__init__()
        self.text = text
        self.voice = voice
        self.rate = rate
        self.save_path = save_path

    def run(self):
        try:
            comm = edge_tts.Communicate(self.text, self.voice, rate=self.rate)
            asyncio.run(comm.save(self.save_path))
            self.finished_signal.emit("✅ 生成成功：" + self.save_path)
        except Exception as e:
            self.finished_signal.emit("❌ 失败：" + str(e))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("多语言文本转MP3工具")
        self.resize(1280, 960)
        self.output_dir = ""

        # ===================== 深色模式样式表【适配Mac深色】 =====================
        style_sheet = """
        *{
            font-family: "PingFang SC", "Microsoft YaHei", sans-serif;
            font-size:12pt;
            color:#f0f0f0;
        }
        QWidget{
            background-color:#1e1e1e;
        }
        QComboBox, QLineEdit, QTextEdit{
            background-color:#2d2d2d;
            border:1px solid #444444;
            border-radius:4px;
            padding:4px;
        }
        QComboBox::drop-down{
            border:none;
        }
        QPushButton{
            font-weight:bold;
            background-color:#2574ed;
            color:white;
            border-radius:4px;
            padding:6px 12px;
            border:none;
        }
        QPushButton:hover{
            background-color:#3482fa;
        }
        QProgressBar{
            border-radius:4px;
            height:10px;
            background:#3a3a3a;
            text-align:center;
        }
        QProgressBar::chunk{
            background:#2574ed;
            border-radius:4px;
        }
        QLabel#copyright_label{
            font-size:10pt;
            color:#aaaaaa;
        }
        """
        self.setStyleSheet(style_sheet)

        # ===================== 完整音色数据 =====================
        self.voice_raw_data = {
            # ========== 英语 en ==========
            "en-AU-NatashaNeural": {"gender": "Female", "desc": "General | Friendly, Positive"},
            "en-AU-WilliamMultilingualNeural": {"gender": "Male", "desc": "General | Friendly, Positive"},
            "en-CA-ClaraNeural": {"gender": "Female", "desc": "General | Friendly, Positive"},
            "en-CA-LiamNeural": {"gender": "Male", "desc": "General | Friendly, Positive"},
            "en-GB-LibbyNeural": {"gender": "Female", "desc": "General | Friendly, Positive"},
            "en-GB-MaisieNeural": {"gender": "Female", "desc": "General | Friendly, Positive"},
            "en-GB-RyanNeural": {"gender": "Male", "desc": "General | Friendly, Positive"},
            "en-GB-SoniaNeural": {"gender": "Female", "desc": "General | Friendly, Positive"},
            "en-GB-ThomasNeural": {"gender": "Male", "desc": "General | Friendly, Positive"},
            "en-HK-SamNeural": {"gender": "Male", "desc": "General | Friendly, Positive"},
            "en-HK-YanNeural": {"gender": "Female", "desc": "General | Friendly, Positive"},
            "en-IE-ConnorNeural": {"gender": "Male", "desc": "General | Friendly, Positive"},
            "en-IE-EmilyNeural": {"gender": "Female", "desc": "General | Friendly, Positive"},
            "en-IN-NeerjaExpressiveNeural": {"gender": "Female", "desc": "General | Friendly, Positive"},
            "en-IN-NeerjaNeural": {"gender": "Female", "desc": "General | Friendly, Positive"},
            "en-IN-PrabhatNeural": {"gender": "Male", "desc": "General | Friendly, Positive"},
            "en-KE-AsiliaNeural": {"gender": "Female", "desc": "General | Friendly, Positive"},
            "en-KE-ChilembaNeural": {"gender": "Male", "desc": "General | Friendly, Positive"},
            "en-NG-AbeoNeural": {"gender": "Male", "desc": "General | Friendly, Positive"},
            "en-NG-EzinneNeural": {"gender": "Female", "desc": "General | Friendly, Positive"},
            "en-NZ-MitchellNeural": {"gender": "Male", "desc": "General | Friendly, Positive"},
            "en-NZ-MollyNeural": {"gender": "Female", "desc": "General | Friendly, Positive"},
            "en-PH-JamesNeural": {"gender": "Male", "desc": "General | Friendly, Positive"},
            "en-PH-RosaNeural": {"gender": "Female", "desc": "General | Friendly, Positive"},
            "en-SG-LunaNeural": {"gender": "Female", "desc": "General | Friendly, Positive"},
            "en-SG-WayneNeural": {"gender": "Male", "desc": "General | Friendly, Positive"},
            "en-TZ-ElimuNeural": {"gender": "Male", "desc": "General | Friendly, Positive"},
            "en-TZ-ImaniNeural": {"gender": "Female", "desc": "General | Friendly, Positive"},
            "en-US-AnaNeural": {"gender": "Female", "desc": "Cartoon, Conversation | Cute"},
            "en-US-AndrewMultilingualNeural": {"gender": "Male", "desc": "Conversation, Copilot | Warm, Confident, Authentic, Honest"},
            "en-US-AndrewNeural": {"gender": "Male", "desc": "Conversation, Copilot | Warm, Confident, Authentic, Honest"},
            "en-US-AriaNeural": {"gender": "Female", "desc": "News, Novel | Positive, Confident"},
            "en-US-AvaMultilingualNeural": {"gender": "Female", "desc": "Conversation, Copilot | Expressive, Caring, Pleasant, Friendly"},
            "en-US-AvaNeural": {"gender": "Female", "desc": "Conversation, Copilot | Expressive, Caring, Pleasant, Friendly"},
            "en-US-BrianMultilingualNeural": {"gender": "Male", "desc": "Conversation, Copilot | Approachable, Casual, Sincere"},
            "en-US-BrianNeural": {"gender": "Male", "desc": "Conversation, Copilot | Approachable, Casual, Sincere"},
            "en-US-ChristopherNeural": {"gender": "Male", "desc": "News, Novel | Reliable, Authority"},
            "en-US-EmmaMultilingualNeural": {"gender": "Female", "desc": "Conversation, Copilot | Cheerful, Clear, Conversational"},
            "en-US-EmmaNeural": {"gender": "Female", "desc": "Conversation, Copilot | Cheerful, Clear, Conversational"},
            "en-US-EricNeural": {"gender": "Male", "desc": "News, Novel | Rational"},
            "en-US-GuyNeural": {"gender": "Male", "desc": "News, Novel | Passion"},
            "en-US-JennyNeural": {"gender": "Female", "desc": "General | Friendly, Considerate, Comfort"},
            "en-US-MichelleNeural": {"gender": "Female", "desc": "News, Novel | Friendly, Pleasant"},
            "en-US-RogerNeural": {"gender": "Male", "desc": "News, Novel | Lively"},
            "en-US-SteffanNeural": {"gender": "Male", "desc": "News, Novel | Rational"},
            "en-ZA-LeahNeural": {"gender": "Female", "desc": "General | Friendly, Positive"},
            "en-ZA-LukeNeural": {"gender": "Male", "desc": "General | Friendly, Positive"},

            # ========== 日语 ja-JP ==========
            "ja-JP-KeitaNeural": {"gender": "Male", "desc": "General | Friendly, Positive"},
            "ja-JP-NanamiNeural": {"gender": "Female", "desc": "General | Friendly, Positive"},

            # ========== 韩语 ko-KR ==========
            "ko-KR-HyunsuMultilingualNeural": {"gender": "Male", "desc": "General | Friendly, Positive"},
            "ko-KR-InJoonNeural": {"gender": "Male", "desc": "General | Friendly, Positive"},
            "ko-KR-SunHiNeural": {"gender": "Female", "desc": "General | Friendly, Positive"},

            # ========== 法语 fr ==========
            "fr-BE-CharlineNeural": {"gender": "Female", "desc": "General | Friendly, Positive"},
            "fr-BE-GerardNeural": {"gender": "Male", "desc": "General | Friendly, Positive"},
            "fr-CA-AntoineNeural": {"gender": "Male", "desc": "General | Friendly, Positive"},
            "fr-CA-JeanNeural": {"gender": "Male", "desc": "General | Friendly, Positive"},
            "fr-CA-SylvieNeural": {"gender": "Female", "desc": "General | Friendly, Positive"},
            "fr-CA-ThierryNeural": {"gender": "Male", "desc": "General | Friendly, Positive"},
            "fr-CH-ArianeNeural": {"gender": "Female", "desc": "General | Friendly, Positive"},
            "fr-CH-FabriceNeural": {"gender": "Male", "desc": "General | Friendly, Positive"},
            "fr-FR-DeniseNeural": {"gender": "Female", "desc": "General | Friendly, Positive"},
            "fr-FR-EloiseNeural": {"gender": "Female", "desc": "General | Friendly, Positive"},
            "fr-FR-HenriNeural": {"gender": "Male", "desc": "General | Friendly, Positive"},
            "fr-FR-RemyMultilingualNeural": {"gender": "Male", "desc": "General | Friendly, Positive"},
            "fr-FR-VivienneMultilingualNeural": {"gender": "Female", "desc": "General | Friendly, Positive"},

            # ========== 意大利语 it-IT ==========
            "it-IT-DiegoNeural": {"gender": "Male", "desc": "General | Friendly, Positive"},
            "it-IT-ElsaNeural": {"gender": "Female", "desc": "General | Friendly, Positive"},
            "it-IT-GiuseppeMultilingualNeural": {"gender": "Male", "desc": "General | Friendly, Positive"},
            "it-IT-IsabellaNeural": {"gender": "Female", "desc": "General | Friendly, Positive"},

            # ========== 西班牙语 es ==========
            "es-AR-ElenaNeural": {"gender": "Female", "desc": "General | Friendly, Positive"},
            "es-AR-TomasNeural": {"gender": "Male", "desc": "General | Friendly, Positive"},
            "es-BO-MarceloNeural": {"gender": "Male", "desc": "General | Friendly, Positive"},
            "es-BO-SofiaNeural": {"gender": "Female", "desc": "General | Friendly, Positive"},
            "es-CL-CatalinaNeural": {"gender": "Female", "desc": "General | Friendly, Positive"},
            "es-CL-LorenzoNeural": {"gender": "Male", "desc": "General | Friendly, Positive"},
            "es-CO-GonzaloNeural": {"gender": "Male", "desc": "General | Friendly, Positive"},
            "es-CO-SalomeNeural": {"gender": "Female", "desc": "General | Friendly, Positive"},
            "es-CR-JuanNeural": {"gender": "Male", "desc": "General | Friendly, Positive"},
            "es-CR-MariaNeural": {"gender": "Female", "desc": "General | Friendly, Positive"},
            "es-CU-BelkysNeural": {"gender": "Female", "desc": "General | Friendly, Positive"},
            "es-CU-ManuelNeural": {"gender": "Male", "desc": "General | Friendly, Positive"},
            "es-DO-EmilioNeural": {"gender": "Male", "desc": "General | Friendly, Positive"},
            "es-DO-RamonaNeural": {"gender": "Female", "desc": "General | Friendly, Positive"},
            "es-EC-AndreaNeural": {"gender": "Female", "desc": "General | Friendly, Positive"},
            "es-EC-LuisNeural": {"gender": "Male", "desc": "General | Friendly, Positive"},
            "es-ES-AlvaroNeural": {"gender": "Male", "desc": "General | Friendly, Positive"},
            "es-ES-ElviraNeural": {"gender": "Female", "desc": "General | Friendly, Positive"},
            "es-ES-XimenaNeural": {"gender": "Female", "desc": "General | Friendly, Positive"},
            "es-GQ-JavierNeural": {"gender": "Male", "desc": "General | Friendly, Positive"},
            "es-GQ-TeresaNeural": {"gender": "Female", "desc": "General | Friendly, Positive"},
            "es-GT-AndresNeural": {"gender": "Male", "desc": "General | Friendly, Positive"},
            "es-GT-MartaNeural": {"gender": "Female", "desc": "General | Friendly, Positive"},
            "es-HN-CarlosNeural": {"gender": "Male", "desc": "General | Friendly, Positive"},
            "es-HN-KarlaNeural": {"gender": "Female", "desc": "General | Friendly, Positive"},
            "es-MX-DaliaNeural": {"gender": "Female", "desc": "General | Friendly, Positive"},
            "es-MX-JorgeNeural": {"gender": "Male", "desc": "General | Friendly, Positive"},
            "es-NI-FedericoNeural": {"gender": "Male", "desc": "General | Friendly, Positive"},
            "es-NI-YolandaNeural": {"gender": "Female", "desc": "General | Friendly, Positive"},
            "es-PA-MargaritaNeural": {"gender": "Female", "desc": "General | Friendly, Positive"},
            "es-PA-RobertoNeural": {"gender": "Male", "desc": "General | Friendly, Positive"},
            "es-PE-AlexNeural": {"gender": "Male", "desc": "General | Friendly, Positive"},
            "es-PE-CamilaNeural": {"gender": "Female", "desc": "General | Friendly, Positive"},
            "es-PR-KarinaNeural": {"gender": "Female", "desc": "General | Friendly, Positive"},
            "es-PR-VictorNeural": {"gender": "Male", "desc": "General | Friendly, Positive"},
            "es-PY-MarioNeural": {"gender": "Male", "desc": "General | Friendly, Positive"},
            "es-PY-TaniaNeural": {"gender": "Female", "desc": "General | Friendly, Positive"},
            "es-SV-LorenaNeural": {"gender": "Female", "desc": "General | Friendly, Positive"},
            "es-SV-RodrigoNeural": {"gender": "Male", "desc": "General | Friendly, Positive"},
            "es-US-AlonsoNeural": {"gender": "Male", "desc": "General | Friendly, Positive"},
            "es-US-PalomaNeural": {"gender": "Female", "desc": "General | Friendly, Positive"},
            "es-UY-MateoNeural": {"gender": "Male", "desc": "General | Friendly, Positive"},
            "es-UY-ValentinaNeural": {"gender": "Female", "desc": "General | Friendly, Positive"},
            "es-VE-PaolaNeural": {"gender": "Female", "desc": "General | Friendly, Positive"},
            "es-VE-SebastianNeural": {"gender": "Male", "desc": "General | Friendly, Positive"},

            # ========== 中文 zh ==========
            "zh-CN-XiaoxiaoNeural": {"gender": "Female", "desc": "News, Novel | Warm"},
            "zh-CN-XiaoyiNeural": {"gender": "Female", "desc": "Cartoon, Novel | Lively"},
            "zh-CN-YunjianNeural": {"gender": "Male", "desc": "Sports, Novel | Passion"},
            "zh-CN-YunxiNeural": {"gender": "Male", "desc": "Novel | Lively, Sunshine"},
            "zh-CN-YunxiaNeural": {"gender": "Male", "desc": "Cartoon, Novel | Cute"},
            "zh-CN-YunyangNeural": {"gender": "Male", "desc": "News | Professional, Reliable"},
            "zh-CN-liaoning-XiaobeiNeural": {"gender": "Female", "desc": "Dialect | Humorous"},
            "zh-CN-shaanxi-XiaoniNeural": {"gender": "Female", "desc": "Dialect | Bright"},
            "zh-HK-HiuGaaiNeural": {"gender": "Female", "desc": "General | Friendly, Positive"},
            "zh-HK-HiuMaanNeural": {"gender": "Female", "desc": "General | Friendly, Positive"},
            "zh-HK-WanLungNeural": {"gender": "Male", "desc": "General | Friendly, Positive"},
            "zh-TW-HsiaoChenNeural": {"gender": "Female", "desc": "General | Friendly, Positive"},
            "zh-TW-HsiaoYuNeural": {"gender": "Female", "desc": "General | Friendly, Positive"},
            "zh-TW-YunJheNeural": {"gender": "Male", "desc": "General | Friendly, Positive"},
        }

        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)
        self.setCentralWidget(widget)

        # ========== 第一行：语言、性别、音色、语速【重点修改spacing=4】 ==========
        row1 = QHBoxLayout()
        row1.setSpacing(4) # ← 缩小标签与输入框间距，由10→4，紧贴不拥挤

        self.lang_combo = QComboBox()
        self.lang_combo.addItems([
            "请选择",
            "英语 (en)",
            "日语 (ja)",
            "韩语 (ko)",
            "法语 (fr)",
            "意大利语 (it)",
            "西班牙语 (es)",
            "中文 (zh)"
        ])

        self.gender_combo = QComboBox()
        self.gender_combo.addItems(["请选择"])
        self.gender_combo.setEnabled(False)

        self.voice_combo = QComboBox()
        self.voice_combo.addItems(["请选择"])
        self.voice_combo.setEnabled(False)

        self.rate_edit = QLineEdit("+0%")
        self.rate_edit.setFixedWidth(160)

        row1.addWidget(QLabel("语言:"))
        row1.addWidget(self.lang_combo)
        row1.addWidget(QLabel("性别:"))
        row1.addWidget(self.gender_combo)
        row1.addWidget(QLabel("音色:"))
        row1.addWidget(self.voice_combo)
        row1.addWidget(QLabel("语速(±%):"))
        row1.addWidget(self.rate_edit)

        # 音色介绍标签
        self.voice_desc_label = QLabel("【音色信息】请选择音色")

        row2 = QHBoxLayout()
        row2.setSpacing(4) # ←同步缩小间距
        self.dir_edit = QLineEdit()
        self.dir_edit.setReadOnly(True)
        btn_select_dir = QPushButton("选择输出目录")
        btn_select_dir.clicked.connect(self.select_folder)
        row2.addWidget(self.dir_edit)
        row2.addWidget(btn_select_dir)

        row3 = QHBoxLayout()
        row3.setSpacing(4) # ←同步缩小间距
        self.fname_edit = QLineEdit("audio")
        row3.addWidget(QLabel("文件名："))
        row3.addWidget(self.fname_edit)

        self.text_input = QTextEdit()
        self.text_input.setPlaceholderText("粘贴文本（中文/英文/日语/韩语/法语/西语/意大利语）...")

        # 百分比进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setRange(0, 100)

        self.status_label = QLabel("就绪")
        btn_gen = QPushButton("生成MP3")
        btn_gen.clicked.connect(self.generate_audio)

        # 底部版权声明
        self.copyright_label = QLabel("""1. 本软件可免费自由传播使用
2. 未经授权严禁售卖，侵权行为我方将依法追究法律责任
作者：一直要求进步的昌强同学""")
        self.copyright_label.setObjectName("copyright_label")

        layout.addLayout(row1)
        layout.addWidget(self.voice_desc_label)
        layout.addLayout(row2)
        layout.addLayout(row3)
        layout.addWidget(self.text_input)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.status_label)
        layout.addWidget(btn_gen)
        layout.addSpacing(18)
        layout.addWidget(self.copyright_label)

        # 绑定筛选事件
        self.lang_combo.currentTextChanged.connect(self.on_language_changed)
        self.gender_combo.currentTextChanged.connect(self.refresh_voice_list)
        self.voice_combo.currentTextChanged.connect(self.update_desc)

        self.refresh_voice_list()

    def on_language_changed(self):
        self.gender_combo.clear()
        self.gender_combo.addItems(["请选择", "Male", "Female"])
        self.gender_combo.setEnabled(self.lang_combo.currentText() != "请选择")

        self.voice_combo.clear()
        self.voice_combo.addItems(["请选择"])
        self.voice_combo.setEnabled(False)
        self.update_desc("")

    def refresh_voice_list(self):
        lang_sel = self.lang_combo.currentText()
        gender_sel = self.gender_combo.currentText()
        self.voice_combo.clear()
        self.voice_combo.addItems(["请选择"])

        if lang_sel == "请选择" or gender_sel == "请选择":
            self.voice_combo.setEnabled(False)
            self.update_desc("")
            return

        candidates = []
        prefix_map = {
            "英语 (en)": "en",
            "日语 (ja)": "ja",
            "韩语 (ko)": "ko",
            "法语 (fr)": "fr",
            "意大利语 (it)": "it",
            "西班牙语 (es)": "es",
            "中文 (zh)": "zh"
        }
        target_prefix = prefix_map.get(lang_sel, None)

        for voice_name, info in self.voice_raw_data.items():
            match_lang = voice_name.startswith(target_prefix)
            match_gender = info["gender"] == gender_sel
            if match_lang and match_gender:
                candidates.append(voice_name)

        self.voice_combo.addItems(candidates)
        self.voice_combo.setEnabled(True)
        self.update_desc(self.voice_combo.currentText())

    def update_desc(self, voice_name):
        if not voice_name or voice_name not in self.voice_raw_data:
            self.voice_desc_label.setText("【音色信息】请选择音色")
            return
        d = self.voice_raw_data[voice_name]
        self.voice_desc_label.setText(f"【音色信息】{d['gender']} | {d['desc']}")

    def select_folder(self):
        path = QFileDialog.getExistingDirectory(self, "选择文件夹")
        if path:
            self.output_dir = path
            self.dir_edit.setText(path)

    def text_language_validate(self, text, lang_option):
        error_list = []
        lines = text.splitlines()

        re_chinese = re.compile(r'[\u4e00-\u9fff，。！？；：""''（）【】、]')
        re_english = re.compile(r'[a-zA-Z,.!?;:\'"() ]')
        re_japanese = re.compile(r'[\u3040-\u309f\u30a0-\u30ff\u4e00-\u9fff､。！？]')
        re_korean = re.compile(r'[\uac00-\ud7af\u3130-\u318f]')
        re_latin_ext = re.compile(r'[a-zA-Zàáâäãåąčćęèéêëėįìíîïłńòóôöõøùúûüųūÿýżźñçčšž,.!?;:\'"() ]')

        for line_num, line in enumerate(lines, start=1):
            char_index = 0
            for char in line:
                char_index += 1
                matched = False
                if lang_option == "中文 (zh)":
                    if re_chinese.match(char):
                        matched = True
                elif lang_option == "英语 (en)":
                    if re_english.match(char):
                        matched = True
                elif lang_option == "日语 (ja)":
                    if re_japanese.match(char):
                        matched = True
                elif lang_option == "韩语 (ko)":
                    if re_korean.match(char):
                        matched = True
                elif lang_option in ("法语 (fr)", "意大利语 (it)", "西班牙语 (es)"):
                    if re_latin_ext.match(char):
                        matched = True

                if not matched and char.strip() != "":
                    context_len = 12
                    start_pos = max(0, char_index - context_len)
                    context_text = line[start_pos:char_index].strip()
                    error_list.append(f"第{line_num}行，「{context_text}」后出现不符合{lang_option.split(' ')[0]}语言的字符「{char}」")
        return error_list

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
        if voice == "请选择":
            QMessageBox.warning(self, "提示", "请筛选并选择音色！")
            return

        err_items = self.text_language_validate(text, lang_selected)
        if err_items:
            msg_content = "\n".join(err_items)
            QMessageBox.warning(self, "文本语言校验失败", msg_content)
            return

        fname = self.fname_edit.text().strip()
        if not fname:
            fname = "audio"
        if not fname.lower().endswith(".mp3"):
            fname += ".mp3"
        full_path = os.path.join(self.output_dir, fname)

        rate = self.rate_edit.text()
        self.status_label.setText("⏳ 正在生成音频...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

        self.worker = TTSWorker(text, voice, rate, full_path)
        self.worker.finished_signal.connect(self.on_complete)
        self.worker.start()

    def on_complete(self, msg):
        self.progress_bar.setValue(100)
        self.status_label.setText(msg)
        if "✅" in msg:
            QMessageBox.information(self, "完成", msg)
        else:
            QMessageBox.critical(self, "错误", msg)


if __name__ == "__main__":
    app = QApplication([])
    app.setStyle("Fusion")
    win = MainWindow()
    win.show()
    app.exec()