"""
文本语言校验逻辑

从 UI 类里抽出来，方便：
  1. 单独写单元测试（tests/test_validator.py）
  2. 以后如果做成 CLI 版本 / Web 服务，也能直接复用这段逻辑
"""
import re
from dataclasses import dataclass
from typing import List

_RE_CHINESE = re.compile(r'[\u4e00-\u9fff，。！？；：""''（）【】、]')
_RE_ENGLISH = re.compile(r'[a-zA-Z,.!?;:\'"() ]')
_RE_JAPANESE = re.compile(r'[\u3040-\u309f\u30a0-\u30ff\u4e00-\u9fff､。！？]')
_RE_KOREAN = re.compile(r'[\uac00-\ud7af\u3130-\u318f]')
_RE_LATIN_EXT = re.compile(
    r'[a-zA-Zàáâäãåąčćęèéêëėįìíîïłńòóôöõøùúûüųūÿýżźñçčšž,.!?;:\'"() ]'
)

_LATIN_LANGS = {"法语 (fr)", "意大利语 (it)", "西班牙语 (es)"}


@dataclass
class ValidationError:
    line_number: int
    context: str
    bad_char: str

    def format(self, lang_label: str) -> str:
        lang_short = lang_label.split(" ")[0]
        return f"第{self.line_number}行，「{self.context}」后出现不符合{lang_short}语言的字符「{self.bad_char}」"


def _match_char(char: str, lang_label: str) -> bool:
    if lang_label == "中文 (zh)":
        return bool(_RE_CHINESE.match(char))
    if lang_label == "英语 (en)":
        return bool(_RE_ENGLISH.match(char))
    if lang_label == "日语 (ja)":
        return bool(_RE_JAPANESE.match(char))
    if lang_label == "韩语 (ko)":
        return bool(_RE_KOREAN.match(char))
    if lang_label in _LATIN_LANGS:
        return bool(_RE_LATIN_EXT.match(char))
    return True  # 未知语言标签，不做校验


def validate_text_language(text: str, lang_label: str, context_len: int = 12) -> List[ValidationError]:
    """
    校验文本中每个字符是否符合所选语言的字符集。
    返回校验错误列表；为空表示校验通过。
    """
    errors: List[ValidationError] = []
    for line_num, line in enumerate(text.splitlines(), start=1):
        for char_index, char in enumerate(line, start=1):
            if char.strip() == "":
                continue
            if _match_char(char, lang_label):
                continue
            start_pos = max(0, char_index - context_len)
            context_text = line[start_pos:char_index].strip()
            errors.append(ValidationError(line_num, context_text, char))
    return errors


def format_errors(errors: List[ValidationError], lang_label: str) -> str:
    return "\n".join(e.format(lang_label) for e in errors)
