"""
文本语言校验逻辑

从 UI 类里抽出来，方便：
  1. 单独写单元测试（tests/test_validator.py）
  2. 以后如果做成 CLI 版本 / Web 服务，也能直接复用这段逻辑

校验策略：每个语言定义"允许的字符"正则，凡是匹配不上的字符（跳过空白）
就报校验错误。数字、连字符、通用标点对各语言都放行。
"""
import re
from dataclasses import dataclass
from typing import List

# 各语言特有字符
_RE_CHINESE = re.compile(
    r'[一-鿿㐀-䶿'
    r'，。！？；：""''（）【】、'
    r'《》…—～·]'
)
_RE_JAPANESE = re.compile(
    r'[぀-ゟ゠-ヿ一-鿿'
    r'｡｢｣､･ｦｧｨｩｪｫｬｭｮｯ'
    r'ｰｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿ'
    r'ﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎﾏ'
    r'ﾐﾑﾒﾓﾔﾕﾖﾗﾘﾙﾚﾛﾜﾝ'
    r'〜。、！？]'
)
_RE_KOREAN = re.compile(
    r'[가-힯㄰-㆏'
    r'。！？，、·]'
)

# 拉丁语系（英/法/意/西）共用：字母 + 带音符字母 + 本语种标点
_RE_LATIN_BASE = (
    r"[a-zA-Z0-9"
    r"àáâäãåąăāæ"
    r"ÀÁÂÄÃÅĄĂĀÆ"
    r"çćčĉċ"
    r"ÇĆČĈĊ"
    r"èéêëēėęěĕ"
    r"ÈÉÊËĒĖĘĚĔ"
    r"ìíîïīįĭ"
    r"ÌÍÎÏĪĮĬ"
    r"łľĺļ"
    r"ŁĽĹĻ"
    r"ñńňņŋ"
    r"ÑŃŇŅŊ"
    r"òóôöõøōőŏ"
    r"ÒÓÔÖÕØŌŐŎ"
    r"ùúûüūųůűŭ"
    r"ÙÚÛÜŪŲŮŰŬ"
    r"ýÿŷ"
    r"ÝŸŶ"
    r"żźž"
    r"ŻŹŽ"
    r"ß"
    r"šśŝşș"
    r"ŠŚŜŞȘ"
    r"ğ"
    r"Ğ"
    r"]"
)

# 各语种特有字母
_RE_FRENCH_EXTRA = re.compile(r"[œæŒÆ]")
_RE_SPANISH_EXTRA = re.compile(r"[¿¡]")

# 对所有语言都放行的：数字、通用标点
_RE_UNIVERSAL = re.compile(
    r"[0-9"
    r".,!?;:\'\"()\[\]{}"
    r"\-–—/@#$%&*+=<>"
    r" "  # non-breaking space
    r" ]"
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
    if _RE_UNIVERSAL.match(char):
        return True
    if lang_label == "中文 (zh)":
        return bool(_RE_CHINESE.match(char))
    if lang_label == "英语 (en)":
        return bool(re.match(_RE_LATIN_BASE, char))
    if lang_label == "日语 (ja)":
        return bool(_RE_JAPANESE.match(char))
    if lang_label == "韩语 (ko)":
        return bool(_RE_KOREAN.match(char))
    if lang_label == "法语 (fr)":
        return bool(re.match(_RE_LATIN_BASE, char) or _RE_FRENCH_EXTRA.match(char))
    if lang_label == "意大利语 (it)":
        return bool(re.match(_RE_LATIN_BASE, char))
    if lang_label == "西班牙语 (es)":
        return bool(re.match(_RE_LATIN_BASE, char) or _RE_SPANISH_EXTRA.match(char))
    return True


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
