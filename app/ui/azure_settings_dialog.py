"""Azure 语音服务设置对话框"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QComboBox, QPushButton, QMessageBox,
)

from app.core.settings_manager import SettingsManager

AZURE_REGIONS = [
    "eastasia",
    "southeastasia",
    "australiaeast",
    "centralindia",
    "japaneast",
    "japanwest",
    "koreacentral",
    "eastus",
    "eastus2",
    "westus",
    "westus2",
    "westus3",
    "centralus",
    "northcentralus",
    "southcentralus",
    "westeurope",
    "northeurope",
    "uksouth",
    "francecentral",
    "germanywestcentral",
    "switzerlandnorth",
    "brazilsouth",
]


class AzureSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        # 复用父窗口的 SettingsManager，确保配置全局一致
        if parent and hasattr(parent, 'settings'):
            self.settings = parent.settings
        else:
            self.settings = SettingsManager()
        self.setWindowTitle("Azure 语音服务设置")
        self.setFixedSize(420, 260)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        title = QLabel("Azure 语音服务设置")
        title.setAlignment(Qt.AlignCenter)
        title.setObjectName("aboutName")

        form = QFormLayout()
        form.setSpacing(10)

        self.key_edit = QLineEdit()
        self.key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_edit.setPlaceholderText("请输入 Azure Speech API Key")
        saved_key = self.settings.get("azure_speech_key") or ""
        if saved_key:
            self.key_edit.setText(saved_key)

        self.region_combo = QComboBox()
        self.region_combo.setEditable(True)
        self.region_combo.addItems(AZURE_REGIONS)
        saved_region = self.settings.get("azure_speech_region") or "eastasia"
        idx = self.region_combo.findText(saved_region)
        if idx >= 0:
            self.region_combo.setCurrentIndex(idx)
        else:
            self.region_combo.setCurrentText(saved_region)

        form.addRow("API Key：", self.key_edit)
        form.addRow("Region：", self.region_combo)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        btn_test = QPushButton("测试连接")
        btn_test.setObjectName("secondaryButton")
        btn_test.clicked.connect(self._test_connection)

        btn_cancel = QPushButton("取消")
        btn_cancel.setObjectName("secondaryButton")
        btn_cancel.clicked.connect(self.reject)

        btn_save = QPushButton("保存")
        btn_save.clicked.connect(self._save_and_accept)

        btn_row.addWidget(btn_test)
        btn_row.addStretch()
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_save)

        layout.addWidget(title)
        layout.addLayout(form)
        layout.addStretch()
        layout.addLayout(btn_row)

    def _save_and_accept(self):
        key = self.key_edit.text().strip()
        region = self.region_combo.currentText().strip()
        if not key:
            QMessageBox.warning(self, "提示", "请输入 API Key")
            return
        if not region:
            QMessageBox.warning(self, "提示", "请选择或输入 Region")
            return
        self.settings.set("azure_speech_key", key)
        self.settings.set("azure_speech_region", region)
        self.settings.save()
        self.accept()

    def _test_connection(self):
        key = self.key_edit.text().strip()
        region = self.region_combo.currentText().strip()
        if not key or not region:
            QMessageBox.warning(self, "提示", "请先填写 API Key 和 Region")
            return

        try:
            import azure.cognitiveservices.speech as speechsdk
        except ImportError:
            QMessageBox.critical(
                self, "错误",
                "未安装 Azure 语音 SDK，请运行: pip install azure-cognitiveservices-speech",
            )
            return

        try:
            speech_config = speechsdk.SpeechConfig(subscription=key, region=region)
            # 用一段短文本做识别测试
            recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config)
            result = recognizer.recognize_once()
            if result.reason in (
                speechsdk.ResultReason.RecognizedSpeech,
                speechsdk.ResultReason.NoMatch,
            ):
                QMessageBox.information(self, "连接成功", "Azure 语音服务连接正常！")
            elif result.reason == speechsdk.ResultReason.Canceled:
                details = result.cancellation_details
                QMessageBox.critical(
                    self, "连接失败",
                    f"认证失败：{details.reason}\n{details.error_details or ''}\n\n请检查 API Key 和 Region 是否正确。",
                )
            else:
                QMessageBox.warning(self, "未知结果", f"测试返回：{result.reason}")
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "连接失败", f"无法连接 Azure 语音服务：{e}")
