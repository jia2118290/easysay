"""
用户配置持久化

保存"上次使用的输出目录 / 语言 / 语速"等，下次启动自动恢复，提升体验。
配置文件存放在系统用户数据目录（见 app/config.py::user_data_dir），
不写入安装目录，避免 Windows 权限问题。
"""
import json
from pathlib import Path
from typing import Any, Dict

from app.config import SETTINGS_FILE_PATH

_DEFAULTS: Dict[str, Any] = {
    "last_output_dir": "",
    "last_lang": "请选择",
    "last_rate": "+0%",
    "last_filename": "audio",
    "last_pause": "无停顿",
    "azure_speech_key": "",
    "azure_speech_region": "eastasia",
    "azure_audio_dir": "",
}


class SettingsManager:
    def __init__(self, path: Path = SETTINGS_FILE_PATH):
        self._path = path
        self._data: Dict[str, Any] = dict(_DEFAULTS)
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                self._data.update(saved)
            except (json.JSONDecodeError, OSError):
                # 配置文件损坏时不影响启动，静默回退默认值
                pass

    def save(self) -> None:
        try:
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
        except OSError:
            pass  # 保存失败不影响主流程，静默忽略

    def get(self, key: str) -> Any:
        return self._data.get(key, _DEFAULTS.get(key))

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
