"""
全局配置模块
- 统一管理资源路径（兼容开发环境 & PyInstaller 打包后的环境）
- 统一管理用户数据目录（配置文件、缓存等，不能写到安装目录）
- 软件基础信息（名称、版本号等）
"""
import os
import sys
from pathlib import Path

# ===================== 软件基础信息 =====================
APP_NAME = "EasySay"
APP_DISPLAY_NAME = "EasySay 多语言文本转MP3工具"
APP_VERSION = "1.0.0"
APP_AUTHOR = "一直要求进步的昌强同学"
APP_ORG = "EasySayStudio"


def resource_path(relative_path: str) -> str:
    """
    解析资源文件的绝对路径。

    - 开发环境下：相对项目根目录解析
    - PyInstaller 打包后：资源被解压到 sys._MEIPASS 临时目录，需要从这里解析

    用法：resource_path("app/resources/icons/app.ico")
    """
    if hasattr(sys, "_MEIPASS"):
        base_path = Path(sys._MEIPASS)  # type: ignore[attr-defined]
    else:
        # config.py 位于 app/ 目录下，项目根目录是它的上一级
        base_path = Path(__file__).resolve().parent.parent
    return str(base_path / relative_path)


def user_data_dir() -> Path:
    """
    返回当前系统下，软件可写的用户数据目录（用于存配置、日志等）。
    绝不要往程序安装目录里写文件，Windows 下大概率没有权限。
    """
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home())) / APP_ORG / APP_NAME
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support" / APP_ORG / APP_NAME
    else:
        base = Path.home() / ".config" / APP_ORG / APP_NAME
    base.mkdir(parents=True, exist_ok=True)
    return base


# ===================== 常用资源路径 =====================
APP_ICON_ICO = resource_path("app/resources/icons/app.ico")
APP_ICON_ICNS = resource_path("app/resources/icons/app.icns")
APP_ICON_PNG = resource_path("app/resources/icons/app.png")
VOICES_JSON_PATH = resource_path("app/data/voices.json")
DARK_QSS_PATH = resource_path("app/resources/qss/dark.qss")

# 跨平台图标：Windows 用 ico，其余用 png（icns 由打包工具在 App Bundle 层面处理，
# 运行时窗口图标统一用 png 即可，兼容性最好）
APP_ICON_PATH = APP_ICON_ICO if sys.platform == "win32" else APP_ICON_PNG

# 用户配置文件路径
SETTINGS_FILE_PATH = user_data_dir() / "settings.json"


def ffmpeg_path() -> str:
    """
    返回 pydub 可用的 ffmpeg 二进制路径。
    - 打包后：ffmpeg 随包打入 _MEIPASS，从这里解析
    - 开发环境：直接用系统 PATH 中的 ffmpeg
    """
    if hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS)  # type: ignore[attr-defined]
        if sys.platform == "win32":
            return str(base / "ffmpeg" / "ffmpeg.exe")
        return str(base / "ffmpeg" / "ffmpeg")
    return "ffmpeg"


def ffprobe_path() -> str:
    """
    返回 pydub 可用的 ffprobe 二进制路径。
    - 打包后：ffprobe 随包打入 _MEIPASS，从这里解析
    - 开发环境：直接用系统 PATH 中的 ffprobe
    """
    if hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS)  # type: ignore[attr-defined]
        if sys.platform == "win32":
            return str(base / "ffmpeg" / "ffprobe.exe")
        return str(base / "ffmpeg" / "ffprobe")
    return "ffprobe"
