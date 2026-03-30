"""番号字符串解析与规范化（无 Qt 依赖，便于单测与脚本复用）。"""

from __future__ import annotations

import re


def is_valid_serialnumber(code: str) -> bool:
    """
    检查番号是否符合格式：字母+可选数字 前缀，中间 "-"，后面为 1-5 位数字
    如：ABP-123、IPX-1024、SSNI-009、CAWD-999
    """

    pattern = r"^[A-Z]{2,6}-\d{1,5}$"
    return bool(re.match(pattern, code.upper()))


def convert_fanza(serial_number: str) -> str:
    """将传统的番号转化成 fanza 番号模式
    例如 IPX-247   ---->   ipx00247
    """

    lower_code = serial_number.lower()
    converted_code = lower_code.replace("-", "00")
    
    if any(converted_code.startswith(p) for p in ("start", "stars", "star","sdde")):
        converted_code = "1" + converted_code
    return converted_code


def serial_number_equal(A: str, B: str) -> bool:
    """
    比较番号是否相等：
    - 全部小写
    - '-' 替换成 '00'
    """

    def normalize(s: str) -> str:
        return s.lower().replace("-", "00")

    return normalize(A) == normalize(B)


def convert_special_serialnumber(serial_number: str) -> str:
    lower_code = serial_number.lower()
    converted_code = lower_code.replace("-", "")
    return converted_code


def extract_serial_from_string(text: str) -> str | None:
    """从字符串中提取首个番号；支持 IPX-247 或 IPX247，返回标准格式（如 IPX-247）。"""

    if not text or not text.strip():
        return None
    text = text.strip().upper()
    m = re.search(r"[A-Z]{2,6}-\d{1,5}", text)
    if m:
        return m.group(0)
    m = re.search(r"[A-Z]{2,6}\d{1,5}", text)
    if m:
        s = m.group(0)
        return re.sub(r"^([A-Z]+)(\d+)$", r"\1-\2", s)
    return None
