from __future__ import annotations

import re
import unicodedata
from datetime import date

from context_guard.schemas.models import Fact, ProtectedSpan, RiskLevel

_URL = re.compile(r"https?://[^\s)]+|www\.[^\s)]+", re.IGNORECASE)
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_DATE = re.compile(
    r"\b(?:\d{4}-\d{1,2}-\d{1,2}|\d{1,2}/\d{1,2}/\d{4}|\d{1,2}\.\d{1,2}\.\d{4})\b"
    r"|\b(?:January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+\d{1,2},\s+\d{4}\b"
    r"|\b\d{1,2}\s+tháng\s+\d{1,2}\s+năm\s+\d{4}\b",
    re.IGNORECASE,
)
_TIME = re.compile(r"\b\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM)?\b", re.IGNORECASE)
_VERSION = re.compile(
    r"(?<![\w.])v?\d+\.\d+(?:\.\d+)+(?![\w.])|(?<![\w.])(?:Python|Node|CUDA|FastAPI|PyTorch)\s+\d+\.\d+(?:\.\d+)?",
    re.IGNORECASE,
)
_PERCENT = re.compile(
    r"(?<![\w.])\d+(?:[.,]\d+)?\s*(?:%|percent|phần\s*trăm)(?![\w])", re.IGNORECASE
)
_WORD_PERCENT = re.compile(
    r"\b(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|"
    r"twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|"
    r"không|một|hai|ba|bốn|năm|sáu|bảy|tám|chín|mười|"
    r"hai\s+mươi|ba\s+mươi|bốn\s+mươi|năm\s+mươi|sáu\s+mươi|"
    r"bảy\s+mươi|tám\s+mươi|chín\s+mươi)\s+(?:percent|phần\s*trăm)\b",
    re.IGNORECASE,
)
_CURRENCY = re.compile(
    r"(?:[$€£]\s?\d[\d,.]*|\d[\d,.]*\s?(?:USD|VND|EUR|GBP|đồng|triệu đồng|million dollars))\b",
    re.IGNORECASE,
)
_NUMBER = re.compile(r"(?<![\w.])\d+(?:[.,]\d+)*(?![\w.])")
_UNIT = re.compile(
    r"(?<![\w.])\d+(?:[.,]\d+)?\s*(?:GB|MB|TB|KB|ms|μs|us|s|kg|g|km|m|cm|mm|Hz|MHz|GHz)(?![\w])",
    re.IGNORECASE,
)
_PATH = re.compile(r"(?:[A-Za-z]:\\[^\s;,)]+|/(?:[\w.~-]+/)+[\w.~-]+|\.{1,2}/[\w./~-]+)")
_FILENAME = re.compile(r"\b[\w.-]+\.(?:py|json|yaml|yml|txt|csv|toml)\b", re.IGNORECASE)
_CONFIG = re.compile(
    r"(?<!\w)[\w.-]+\s*=\s*(?:true|false|enabled|disabled|[\w./-]+)",
    re.IGNORECASE,
)
_BOOLEAN = re.compile(r"\b(?:true|false|enabled|disabled)\b", re.IGNORECASE)
_FLAG = re.compile(r"(?<!\w)--?[A-Za-z][\w-]*")
_WORD_NUMBER = re.compile(
    r"\b(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|"
    r"twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|"
    r"không|một|hai|ba|bốn|năm|sáu|bảy|tám|chín|mười)\b",
    re.IGNORECASE,
)
_CODE = re.compile(
    r"`[^`]+`|\$\{[A-Z_][A-Z0-9_]*\}|"
    r"\b(?:uv\s+run\s+pytest|python\s+[\w./-]+|pip\s+install\s+[\w.-]+)\b",
    re.IGNORECASE,
)

_PATTERNS: tuple[tuple[str, re.Pattern[str], RiskLevel], ...] = (
    ("url", _URL, RiskLevel.HIGH),
    ("email", _EMAIL, RiskLevel.HIGH),
    ("date", _DATE, RiskLevel.HIGH),
    ("time", _TIME, RiskLevel.MEDIUM),
    ("version", _VERSION, RiskLevel.CRITICAL),
    ("currency", _CURRENCY, RiskLevel.CRITICAL),
    ("percentage", _PERCENT, RiskLevel.CRITICAL),
    ("percentage", _WORD_PERCENT, RiskLevel.CRITICAL),
    ("unit", _UNIT, RiskLevel.HIGH),
    ("path", _PATH, RiskLevel.HIGH),
    ("filename", _FILENAME, RiskLevel.HIGH),
    ("config", _CONFIG, RiskLevel.CRITICAL),
    ("boolean", _BOOLEAN, RiskLevel.CRITICAL),
    ("flag_or_literal", _FLAG, RiskLevel.HIGH),
    ("code", _CODE, RiskLevel.CRITICAL),
    ("number", _WORD_NUMBER, RiskLevel.HIGH),
    ("number", _NUMBER, RiskLevel.HIGH),
)

_VI_HINTS = re.compile(
    r"\b(?:không|chưa|phải|nếu|trừ|ngoại|phần trăm|đồng|tháng|dataset|mô hình)\b", re.I
)
_EN_HINTS = re.compile(r"\b(?:the|not|must|if|unless|percent|dollars|dataset|model|shall)\b", re.I)


def normalize_text(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", text).split())


def detect_language(text: str, requested: str = "auto") -> str:
    if requested in {"vi", "en"}:
        return requested
    vi = len(_VI_HINTS.findall(text))
    en = len(_EN_HINTS.findall(text))
    if vi == en == 0:
        return "en"
    return "vi" if vi >= en else "en"


def _canonical(kind: str, value: str) -> str:
    v = normalize_text(value).lower()
    if kind == "percentage":
        v = v.replace("phần trăm", "%").replace("percent", "%").replace(" ", "")
        word_percent = {
            "zero": "0",
            "one": "1",
            "two": "2",
            "three": "3",
            "four": "4",
            "five": "5",
            "six": "6",
            "seven": "7",
            "eight": "8",
            "nine": "9",
            "ten": "10",
            "twenty": "20",
            "thirty": "30",
            "forty": "40",
            "fifty": "50",
            "sixty": "60",
            "seventy": "70",
            "eighty": "80",
            "ninety": "90",
            "không": "0",
            "một": "1",
            "hai": "2",
            "ba": "3",
            "bốn": "4",
            "năm": "5",
            "sáu": "6",
            "bảy": "7",
            "tám": "8",
            "chín": "9",
            "mười": "10",
            "haimươi": "20",
            "bamươi": "30",
            "bốnmươi": "40",
            "nămmươi": "50",
            "sáumươi": "60",
            "bảymươi": "70",
            "támmươi": "80",
            "chínmươi": "90",
        }
        if v.endswith("%"):
            number = v[:-1]
            v = f"{word_percent.get(number, number)}%"
    if kind in {"flag_or_literal", "url", "email", "path", "version"}:
        return v
    if kind == "date":
        iso = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", v)
        if iso:
            try:
                return date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3))).isoformat()
            except ValueError:
                return v
        slash = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", v)
        if slash and int(slash.group(1)) > 12:
            try:
                return date(
                    int(slash.group(3)), int(slash.group(2)), int(slash.group(1))
                ).isoformat()
            except ValueError:
                return v
        month = re.fullmatch(r"([a-z]+)\s+(\d{1,2}),\s+(\d{4})", v)
        if month:
            months = {
                name.lower(): number
                for number, name in enumerate(
                    (
                        "January",
                        "February",
                        "March",
                        "April",
                        "May",
                        "June",
                        "July",
                        "August",
                        "September",
                        "October",
                        "November",
                        "December",
                    ),
                    1,
                )
            }
            if month.group(1) in months:
                try:
                    return date(
                        int(month.group(3)), months[month.group(1)], int(month.group(2))
                    ).isoformat()
                except ValueError:
                    return v
        vn = re.fullmatch(r"(\d{1,2}) tháng (\d{1,2}) năm (\d{4})", v)
        if vn and int(vn.group(1)) > 12:
            try:
                return date(int(vn.group(3)), int(vn.group(2)), int(vn.group(1))).isoformat()
            except ValueError:
                return v
    if kind == "number" and re.fullmatch(r"\d{1,3}(?:,\d{3})+", v):
        return v.replace(",", "")
    number_words = {
        "zero": "0",
        "one": "1",
        "two": "2",
        "three": "3",
        "four": "4",
        "five": "5",
        "six": "6",
        "seven": "7",
        "eight": "8",
        "nine": "9",
        "ten": "10",
        "không": "0",
        "một": "1",
        "hai": "2",
        "ba": "3",
        "bốn": "4",
        "năm": "5",
        "sáu": "6",
        "bảy": "7",
        "tám": "8",
        "chín": "9",
        "mười": "10",
    }
    if kind == "number" and v in number_words:
        return number_words[v]
    if kind == "code":
        return v.strip("`")
    return v


def extract_facts(
    text: str, language: str = "auto"
) -> tuple[list[Fact], list[ProtectedSpan], list[str], str]:
    normalized_language = detect_language(text, language)
    spans: list[ProtectedSpan] = []
    seen: set[tuple[int, int, str]] = set()
    index = 0
    warnings: list[str] = []
    if not normalize_text(text):
        warnings.append("EMPTY_TEXT")
    for kind, pattern, severity in _PATTERNS:
        for match in pattern.finditer(text):
            key = (match.start(), match.end(), kind)
            if key in seen:
                continue
            if any(
                match.start() < existing.end and existing.start < match.end() for existing in spans
            ):
                continue
            seen.add(key)
            raw = match.group(0)
            if kind == "number" and raw.casefold() == "không":
                # "không" is ambiguous between Vietnamese zero and negation;
                # LogicGuard handles the safety-critical negation interpretation.
                continue
            date_parts = re.fullmatch(r"(\d{1,2})[/.](\d{1,2})[/.]\d{4}", raw)
            ambiguous = bool(
                kind == "date"
                and date_parts
                and int(date_parts.group(1)) <= 12
                and int(date_parts.group(2)) <= 12
            )
            confidence = 0.7 if ambiguous else 1.0
            if ambiguous:
                warnings.append(f"Ambiguous date locale: {raw}")
            if kind == "number" and re.fullmatch(r"\d{1,3}\.\d{3}(?:\.\d{3})*", raw):
                warnings.append(f"Ambiguous numeric locale: {raw}")
            fact_id = f"fact_{index:04d}"
            index += 1
            spans.append(
                ProtectedSpan(
                    id=fact_id,
                    type=kind,
                    text=raw,
                    start=match.start(),
                    end=match.end(),
                    normalized_value=_canonical(kind, raw),
                    severity=severity,
                    confidence=confidence,
                    metadata={"ambiguous_locale": ambiguous},
                )
            )
    spans.sort(key=lambda item: (item.start, item.end, item.type))
    facts = [Fact.model_validate(span.model_dump()) for span in spans]
    return facts, spans, sorted(set(warnings)), normalized_language
