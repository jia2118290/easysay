"""
EasySay 启动入口
只负责创建 QApplication 并显示主窗口，不放任何业务逻辑。
"""
import sys

from PySide6.QtWidgets import QApplication

from app.config import APP_NAME
from app.ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setStyle("Fusion")

    win = MainWindow()
    win.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
