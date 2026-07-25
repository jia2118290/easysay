"""
校验逻辑单元测试
运行：python -m pytest tests/ -v   （或直接 python tests/test_validator.py）
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.validator import validate_text_language  # noqa: E402


def test_chinese_text_passes():
    errors = validate_text_language("你好，世界！", "中文 (zh)")
    assert errors == []


def test_chinese_text_with_english_char_fails():
    errors = validate_text_language("你好abc", "中文 (zh)")
    assert len(errors) == 3  # a, b, c 三个字符不属于中文字符集


def test_english_text_passes():
    errors = validate_text_language("Hello, world!", "英语 (en)")
    assert errors == []


def test_english_text_with_chinese_char_fails():
    errors = validate_text_language("Hello你好", "英语 (en)")
    assert len(errors) == 2


def test_french_accented_chars_pass():
    errors = validate_text_language("Bonjour, ça va très bien.", "法语 (fr)")
    assert errors == []


def test_empty_text_passes():
    errors = validate_text_language("", "中文 (zh)")
    assert errors == []


if __name__ == "__main__":
    test_chinese_text_passes()
    test_chinese_text_with_english_char_fails()
    test_english_text_passes()
    test_english_text_with_chinese_char_fails()
    test_french_accented_chars_pass()
    test_empty_text_passes()
    print("全部测试通过 ✅")
