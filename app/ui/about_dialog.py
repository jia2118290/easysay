"""关于弹窗：展示版本号、作者、版权声明"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout, QPushButton, QHBoxLayout

from app.config import APP_AUTHOR, APP_DISPLAY_NAME, APP_ICON_PNG, APP_VERSION


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("关于 EasySay")
        self.setFixedSize(360, 320)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(10)

        icon_label = QLabel()
        pixmap = QPixmap(APP_ICON_PNG).scaled(
            96, 96, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        icon_label.setPixmap(pixmap)
        icon_label.setAlignment(Qt.AlignCenter)

        name_label = QLabel(APP_DISPLAY_NAME)
        name_label.setAlignment(Qt.AlignCenter)
        name_label.setObjectName("aboutName")

        version_label = QLabel(f"版本 {APP_VERSION}")
        version_label.setAlignment(Qt.AlignCenter)

        author_label = QLabel(f"作者：{APP_AUTHOR}")
        author_label.setAlignment(Qt.AlignCenter)

        notice_label = QLabel(
            "1. 本软件可免费自由传播使用\n"
            "2. 未经授权严禁售卖，侵权行为我方将依法追究法律责任"
        )
        notice_label.setAlignment(Qt.AlignCenter)
        notice_label.setObjectName("aboutNotice")

        btn_layout = QHBoxLayout()
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        btn_layout.addStretch()

        layout.addWidget(icon_label)
        layout.addWidget(name_label)
        layout.addWidget(version_label)
        layout.addWidget(author_label)
        layout.addSpacing(10)
        layout.addWidget(notice_label)
        layout.addLayout(btn_layout)
