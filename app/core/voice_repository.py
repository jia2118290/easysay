"""
音色数据仓库

音色数据被拆到 app/data/voices.json（不再硬编码在 .py 文件里），
好处：
  1. 以后 edge_tts 更新音色列表，只需要替换/追加 json，不用改代码重新发版
  2. 可以支持"检测更新"功能，从远端下载最新的 voices.json 覆盖本地
"""
import json
from pathlib import Path
from typing import Dict, List

from app.config import VOICES_JSON_PATH

# 语言选项 -> edge_tts 语言前缀 的映射，UI 和校验逻辑共用这份映射
LANGUAGE_OPTIONS: Dict[str, str] = {
    "英语 (en)": "en",
    "日语 (ja)": "ja",
    "韩语 (ko)": "ko",
    "法语 (fr)": "fr",
    "意大利语 (it)": "it",
    "西班牙语 (es)": "es",
    "中文 (zh)": "zh",
}


class VoiceRepository:
    """封装音色数据的加载与查询，UI 层不直接接触原始字典结构。"""

    def __init__(self, json_path: str = VOICES_JSON_PATH):
        self._json_path = Path(json_path)
        self._data: Dict[str, dict] = self._load()

    def _load(self) -> Dict[str, dict]:
        if not self._json_path.exists():
            raise FileNotFoundError(
                f"音色数据文件缺失：{self._json_path}\n"
                f"请确认打包时已将 app/data/voices.json 一并包含。"
            )
        with open(self._json_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def reload(self) -> None:
        """重新从磁盘加载（用于"检测更新"覆盖 json 后刷新内存数据）"""
        self._data = self._load()

    @property
    def language_options(self) -> List[str]:
        return list(LANGUAGE_OPTIONS.keys())

    def filter_by(self, lang_label: str, gender: str) -> List[str]:
        """
        按语言标签（如 "英语 (en)"）和性别（"Male"/"Female"）筛选音色名称列表
        """
        prefix = LANGUAGE_OPTIONS.get(lang_label)
        if not prefix:
            return []
        return [
            name
            for name, info in self._data.items()
            if name.startswith(prefix + "-") and info.get("gender") == gender
        ]

    def get_info(self, voice_name: str) -> dict | None:
        return self._data.get(voice_name)

    def describe(self, voice_name: str) -> str:
        info = self.get_info(voice_name)
        if not info:
            return "【音色信息】请选择音色"
        display_name = _localize_name(voice_name)
        return f"【音色信息】{info['gender']} | {display_name} | {info['desc']}"

    def localized_name(self, voice_name: str) -> str:
        return _localize_name(voice_name)


def _localize_name(name: str) -> str:
    parts = name.split("-", 2)
    if len(parts) < 3:
        return name
    locale = f"{parts[0]}-{parts[1]}"
    localized = _LOCALE_MAP.get(locale, locale)
    return f"{localized}-{parts[2]}"


_LOCALE_MAP = {
    "en-US": "美音",
    "en-GB": "英音",
    "en-AU": "澳音",
    "en-CA": "加音",
    "en-IN": "印音",
    "en-HK": "港音",
    "en-IE": "爱尔兰音",
    "en-KE": "肯尼亚音",
    "en-NG": "尼日利亚音",
    "en-NZ": "新西兰音",
    "en-PH": "菲律宾音",
    "en-SG": "新加坡音",
    "en-TZ": "坦桑尼亚音",
    "en-ZA": "南非音",
    "es-ES": "西音",
    "es-MX": "墨音",
    "es-US": "美式西音",
    "es-AR": "阿根廷音",
    "es-BO": "玻利维亚音",
    "es-CL": "智利音",
    "es-CO": "哥伦比亚音",
    "es-CR": "哥斯达黎加音",
    "es-CU": "古巴音",
    "es-DO": "多米尼加音",
    "es-EC": "厄瓜多尔音",
    "es-GQ": "赤道几内亚音",
    "es-GT": "危地马拉音",
    "es-HN": "洪都拉斯音",
    "es-NI": "尼加拉瓜音",
    "es-PA": "巴拿马音",
    "es-PE": "秘鲁音",
    "es-PR": "波多黎各音",
    "es-PY": "巴拉圭音",
    "es-SV": "萨尔瓦多音",
    "es-UY": "乌拉圭音",
    "es-VE": "委内瑞拉音",
    "fr-FR": "法音",
    "fr-CA": "加音",
    "fr-BE": "比利时音",
    "fr-CH": "瑞士音",
    "it-IT": "意音",
    "ja-JP": "日音",
    "ko-KR": "韩音",
    "zh-CN": "中音",
    "zh-TW": "台音",
    "zh-HK": "粤语",
}
