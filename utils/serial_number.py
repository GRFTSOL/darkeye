"""番号字符串解析与规范化（无 Qt 依赖，便于单测与脚本复用）。"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence

_RE_IU = re.IGNORECASE | re.UNICODE

# 与 Electron 侧 @main/utils/subtitles 中 CHINESE_SUBTITLE_* 手工同步；空元组时仅尾部去字幕标签与 TS 可能不一致。
CHINESE_SUBTITLE_FILENAME_TOKEN_HINTS: tuple[str, ...] = ()
CHINESE_SUBTITLE_STRONG_HINTS: tuple[str, ...] = ()

_FILENAME_DELIMITER = r"[-_.\s\[\](){}【】（）]"

_SHORT_TOKEN_PATTERNS: tuple[str, ...] = (
    "4K",
    "4KS",
    "8K",
    "2160P",
    "1080P",
    "720P",
    "HD",
    "HEVC",
    "H264",
    "H265",
    "X264",
    "X265",
    "AAC",
    "DVD",
    "FULL",
)


def _escape_regex(value: str) -> str:
    return re.escape(value)


def _join_regex_alternation(values: Sequence[str]) -> str:
    return "|".join(_escape_regex(v) for v in values)


def _subtitle_token_alternation() -> str:
    merged = [
        *CHINESE_SUBTITLE_FILENAME_TOKEN_HINTS,
        *CHINESE_SUBTITLE_STRONG_HINTS,
    ]
    return _join_regex_alternation(merged) if merged else ""


def _compile_trailing_subtitle_pattern() -> re.Pattern[str] | None:
    alt = _subtitle_token_alternation()
    if not alt:
        return None
    return re.compile(rf"{_FILENAME_DELIMITER}(?:{alt})$", _RE_IU)


_TRAILING_SUBTITLE_RE = _compile_trailing_subtitle_pattern()
_TRAILING_UNCENSORED_RE = re.compile(r"[-_.\s]U$", _RE_IU)
_TRAILING_PART_RE = re.compile(r"[-_.\s](?:CD|PART|EP)[-_\s]?\d{1,2}$", _RE_IU)
_TRAILING_FC2_JP_PART_RE = re.compile(r"[-_.\s](?:前番|前編|後番|後編)$", _RE_IU)
_TRAILING_BARE_PART_RE = re.compile(r"[-_.\s][1-9]$", _RE_IU)
# 文件名尾部 -c C / -C c 等（normalize 大写后均为 -C C）的分碟标记
_TRAILING_C_LETTER_PAIR_RE = re.compile(r"[-_.\s]C[-_.\s]+C$", _RE_IU)
# 常见中字等标签：-ch、.ch、_ch；或紧接在数字后的 ch（如 stars-879ch）
_TRAILING_CH_SUFFIX_RE = re.compile(r"[-_.\s]CH$", _RE_IU)
_TRAILING_CH_AFTER_DIGIT_RE = re.compile(r"(?<=\d)CH$", _RE_IU)
# 分碟：尾部单独 -C（ssni-392-C）；或数字后直接 C（IPX-580C）。须在 -C C 双字母规则之后处理。
_TRAILING_LONE_HYPHEN_C_RE = re.compile(r"[-_.\s]C$", _RE_IU)
_TRAILING_C_AFTER_DIGIT_RE = re.compile(r"(?<=\d)C$", _RE_IU)


def _strip_trailing_tokens(value: str, *, strip_bare_part: bool) -> str:
    current = value
    while True:
        next_s = current
        if _TRAILING_SUBTITLE_RE is not None:
            next_s = _TRAILING_SUBTITLE_RE.sub("", next_s)
        next_s = _TRAILING_UNCENSORED_RE.sub("", next_s)
        next_s = _TRAILING_PART_RE.sub("", next_s)
        next_s = _TRAILING_FC2_JP_PART_RE.sub("", next_s)
        next_s = _TRAILING_C_LETTER_PAIR_RE.sub("", next_s)
        next_s = _TRAILING_CH_SUFFIX_RE.sub("", next_s)
        next_s = _TRAILING_CH_AFTER_DIGIT_RE.sub("", next_s)
        next_s = _TRAILING_LONE_HYPHEN_C_RE.sub("", next_s)
        next_s = _TRAILING_C_AFTER_DIGIT_RE.sub("", next_s)
        stripped = _TRAILING_BARE_PART_RE.sub("", next_s) if strip_bare_part else next_s
        if stripped == current:
            return stripped
        current = stripped


def normalize_raw_name(raw_name: str, escape_strings: Sequence[str] = ()) -> str:
    """与 number.ts 中 normalizeRawName 对齐：NFC 大写、去标签/日期/分集尾缀、分隔符合一为 -。"""

    normalized = unicodedata.normalize("NFC", raw_name).upper()
    for token in escape_strings:
        t = token.strip()
        if not t:
            continue
        normalized = normalized.replace(t.upper(), "")

    for token in _SHORT_TOKEN_PATTERNS:
        normalized = re.sub(
            rf"[-_.\s\[]{re.escape(token)}[-_.\s\]]",
            "-",
            normalized,
            flags=_RE_IU,
        )

    normalized = re.sub(r"FC2[-_ ]?PPV", "FC2-", normalized, flags=_RE_IU)
    normalized = re.sub(r"GACHIPPV", "GACHI", normalized, flags=_RE_IU)
    normalized = re.sub(r"-+", "-", normalized)
    normalized = re.sub(r"\d{4}[-_.]\d{1,2}[-_.]\d{1,2}", "", normalized, flags=_RE_IU)
    # 形如 -[YY-MM-DD] 或 [YY.MM.DD] 的短日期
    normalized = re.sub(
        r"[-\[]\d{2}[-_.]\d{2}[-_.]\d{2}\]?", "", normalized, flags=_RE_IU
    )
    normalized = re.sub(r"[-_.\s][A-Z0-9]\.$", "", normalized, flags=_RE_IU)
    # 品番前目录号：345simm-336、345-simm-336 -> SIMM-336（后面须为字母段）
    normalized = re.sub(r"^\d+[-_.\s]*(?=[A-Z])", "", normalized, flags=_RE_IU)

    normalized = _strip_trailing_tokens(normalized, strip_bare_part=True)
    normalized = re.sub(r"[-_.\s]+", "-", normalized, flags=_RE_IU)
    normalized = re.sub(r"^[-_.\s]+|[-_.\s]+$", "", normalized, flags=_RE_IU)
    return normalized


def normalize_number(value: str) -> str:
    """与 number.ts 中 normalizeNumber 对齐。"""

    s = re.sub(r"FC-", "FC2-", value, flags=re.UNICODE)
    s = re.sub(r"-+", "-", s)
    s = re.sub(r"^[-_.\s]+|[-_.\s]+$", "", s, flags=re.UNICODE)
    return s


# 有序模式与 utils/number.ts extractNumber 中 orderedPatterns 一致；含捕获组时用 _Pat 标记特殊拼接规则。
class _Pat:
    __slots__ = ("kind", "regex")

    def __init__(self, kind: str, regex: str) -> None:
        self.kind = kind
        self.regex = regex


# 与 number.ts 大致一致；Python 侧有意差异（见单行注释）：
# - lazy2/lazy3 提前于 \\d{3,}-[A-Z]{3,}；省略纯 \\d-\\d；增 glued_jav；N\\d{4} 早于 [A-Z]+-[A-Z]\\d+。
_ORDERED_SERIAL_PATTERNS: tuple[_Pat, ...] = (
    _Pat("single", r"(FC2-\d{5,})"),
    _Pat("single", r"(FC2\d{5,})"),
    _Pat("single", r"(HEYZO-\d{3,})"),
    _Pat("single", r"(HEYZO\d{3,})"),
    _Pat("single", r"(TH101-\d{3,}-\d{5,})"),
    _Pat("single", r"(T28-?\d{3,})"),
    _Pat("single", r"(S2M[BD]*-\d{3,})"),
    _Pat("single", r"(MCB3D[BD]*-\d{2,})"),
    _Pat("single", r"(KIN8(?:TENGOKU)?-?\d{3,})"),
    _Pat("single", r"(CW3D2D?BD-?\d{2,})"),
    _Pat("single", r"(MMR-?[A-Z]{2,}-?\d+[A-Z]*)"),
    _Pat("single", r"(XXX-AV-\d{4,})"),
    _Pat("single", r"(MKY-[A-Z]+-\d{3,})"),
    _Pat("fanza00", r"([A-Z]{2,})00(\d{3})"),
    _Pat("single", r"(\d{2,}[A-Z]{2,}-\d{2,}[A-Z]?)"),
    _Pat("single", r"([A-Z]{2,}-\d{2,}[A-Z]?)"),
    # 早于 ([A-Z]+-[A-Z]\d+)，否则 \"FOO-N1234\" 会被整条吞掉
    _Pat("single", r"(?:^|[^A-Z])(N\d{4})(?:[^A-Z]|$)"),
    _Pat("single", r"([A-Z]+-[A-Z]\d+)"),
    # 紧邻 字母+数字，避免 lazy 规则把噪声音词与数字拼成番号
    _Pat("glued_jav", r"([A-Z]{2,6})(\d{1,5})(?=$|[-_\s\[\](){}【】（）]|[A-Z]{2,})"),
    _Pat("lazy2", r"([A-Z]{3,}).*?(\d{2,})"),
    _Pat("lazy3", r"([A-Z]{2,}).*?(\d{3,})"),
    _Pat("single", r"(\d{3,}-[A-Z]{3,})"),
    _Pat("h_prefix", r"H_\d{3,}([A-Z]{2,})(\d{2,})"),
)

_COMPILED_ORDERED = tuple(
    (p, re.compile(p.regex, _RE_IU)) for p in _ORDERED_SERIAL_PATTERNS
)


def _extract_from_normalized(normalized: str) -> str | None:
    for pat, cre in _COMPILED_ORDERED:
        m = cre.search(normalized)
        if not m:
            continue
        if pat.kind == "fanza00":
            raw = f"{m.group(1)}-{m.group(2)}"
            return normalize_number(raw)
        if pat.kind == "glued_jav":
            raw = f"{m.group(1)}-{m.group(2)}"
            return normalize_number(raw)
        if pat.kind == "h_prefix":
            raw = f"{m.group(1)}-{m.group(2)}"
            return normalize_number(raw)
        if pat.kind in ("lazy2", "lazy3"):
            raw = f"{m.group(1)}-{m.group(2)}"
            return normalize_number(raw)
        g1 = m.group(1) if m.lastindex and m.lastindex >= 1 else None
        raw = g1 if g1 is not None else m.group(0)
        # N\d{4} 等整段匹配在 group(1)
        if g1 is None and m.groups():
            raw = next((g for g in m.groups() if g), m.group(0))
        return normalize_number(raw)
    return None


def _fallback_simple_serial(normalized: str) -> str | None:
    m = re.search(r"[A-Z]{2,6}-\d{1,5}", normalized, _RE_IU)
    if m:
        return normalize_number(m.group(0)).upper()
    m = re.search(r"[A-Z]{2,6}\d{1,5}", normalized, _RE_IU)
    if m:
        s = m.group(0)
        fused = re.sub(r"^([A-Z]+)(\d+)$", r"\1-\2", s, flags=_RE_IU)
        return normalize_number(fused).upper()
    return None


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
    这个对接需要查fanza,而且这个还有时效性。
    """

    lower_code = serial_number.lower()
    converted_code = lower_code.replace("-", "00")

    if any(converted_code.startswith(p) for p in ("start", "stars", "star", "sdde","namh")):
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


def extract_serial_from_string(
    text: str | None, escape_strings: Sequence[str] = ()
) -> str | None:
    """从字符串中提取首个番号；逻辑与 utils/number.ts 中 extractNumber 对齐，大写返回。

    无 orderedPatterns 命中时回退为简明 JAV 形式（2–6 字母 + 1–5 位数字），仍无则 None。
    escape_strings 会从规范化前名称中剔除（与 TS escapeStrings 一致）。
    """

    if text is None or not str(text).strip():
        return None
    normalized = normalize_raw_name(str(text).strip(), escape_strings)
    if not normalized:
        return None
    extracted = _extract_from_normalized(normalized)
    if extracted:
        return extracted.upper()
    return _fallback_simple_serial(normalized)
