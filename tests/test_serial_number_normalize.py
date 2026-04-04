"""utils.serial_number：normalize_number / normalize_raw_name 补充用例。"""

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.serial_number import normalize_number, normalize_raw_name  # noqa: E402


@pytest.mark.parametrize(
    "value, expected",
    [
        ("  abc--def  ", "abc-def"),
        ("FC-12345", "FC2-12345"),
        ("prefix-FC-suffix", "prefix-FC2-suffix"),
        ("foo---bar", "foo-bar"),
    ],
)
def test_normalize_number(value, expected):
    assert normalize_number(value) == expected


@pytest.mark.parametrize(
    "raw, expected_substr",
    [
        ("ipx-247", "IPX-247"),
        ("SSNI-392-cd-2", "SSNI-392"),
        ("my-file_U", "MY-FILE"),
        ("SNIS-001 1080P", "SNIS-001"),
        ("345simm-336-final", "SIMM-336-FINAL"),
        ("GACHIPPV-100", "GACHI-100"),
    ],
)
def test_normalize_raw_name_common_cases(raw, expected_substr):
    out = normalize_raw_name(raw)
    assert expected_substr in out or out == expected_substr


def test_normalize_raw_name_escape_strings():
    out = normalize_raw_name(
        "FOO IPX-247 BAR",
        escape_strings=("FOO", "BAR"),
    )
    assert out == "IPX-247"


def test_normalize_raw_name_fc2_variant():
    out = normalize_raw_name("FC2_PPV123456")
    assert "FC2" in out and "123456" in out
