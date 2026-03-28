import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.serial_number import (
    convert_fanza,
    convert_special_serialnumber,
    extract_serial_from_string,
    is_valid_serialnumber,
    serial_number_equal,
)


@pytest.mark.parametrize(
    "code, expected",
    [
        ("ABP-123", True),
        ("IPX-1024", True),
        ("SSNI-009", True),
        ("CAWD-999", True),
        ("abp-123", True),  # 小写也有效
        ("A-123", False),  # 前缀至少2个字母
        ("ABP-123456", False),  # 数字最多5位
        ("ABP123", False),  # 缺少 -
        ("ABP-12A", False),  # 数字中含字母不合法
        ("AB-1", True),  # 两位字母，1位数字
        ("ABCDEFG-123", False),  # 字母超过6位不合法
    ],
)
def test_is_valid_serialnumber(code, expected):
    assert is_valid_serialnumber(code) == expected


@pytest.mark.parametrize(
    "input_code, expected",
    [
        ("IPX-247", "ipx00247"),
        ("ABP-123", "abp00123"),
        ("SSNI-009", "ssni00009"),
        ("CAWD-999", "cawd00999"),
        ("XYZ-1", "xyz001"),
        ("NoDash", "nodash"),
        ("abc-DEF", "abc00def"),
    ],
)
def test_convert_fanza(input_code, expected):
    assert convert_fanza(input_code) == expected


@pytest.mark.parametrize(
    "a, b, expected",
    [
        ("IPX-247", "ipx00247", True),
        ("ipx00247", "IPX-247", True),
        ("ABP-123", "abp00123", True),
        ("SSNI-009", "ssni00009", True),
        ("CAWD-999", "cawd00999", True),
        ("IPX-247", "IPX-248", False),
        ("ABP-123", "ABP-124", False),
        # 无横线形式与带横线形式的规范化不同（- -> 00）
        ("IPX-247", "IPX247", False),
    ],
)
def test_serial_number_equal(a, b, expected):
    assert serial_number_equal(a, b) == expected


@pytest.mark.parametrize(
    "input_code, expected",
    [
        ("IPX-247", "ipx247"),
        ("SSNI-009", "ssni009"),
        ("ABP-123", "abp123"),
        ("CAWD-999", "cawd999"),
        ("abc-DEF", "abcdef"),
    ],
)
def test_convert_special_serialnumber(input_code, expected):
    assert convert_special_serialnumber(input_code) == expected


@pytest.mark.parametrize(
    "text, expected",
    [
        (None, None),
        ("", None),
        ("   ", None),
        ("周边作品 SNIS-456 完结", "SNIS-456"),
        ("无番号字符串", None),
        ("CODE IS IPX247 HERE", "IPX-247"),
        ("CODE IS ipx-247 HERE", "IPX-247"),
        ("先出现 ABC-1 后出现 DEF-9", "ABC-1"),
        ("FG-123 trailing", "FG-123"),
        ("只有横线后数字 123-456", None),
    ],
)
def test_extract_serial_from_string(text, expected):
    assert extract_serial_from_string(text) == expected
