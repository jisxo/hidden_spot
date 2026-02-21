import hashlib
import json
import re
from datetime import datetime
from typing import Any

from bs4 import BeautifulSoup

_PORTAL_NOISE_MARKERS = (
    "본문 바로가기",
    "주 메뉴 바로가기",
    "내정보 보기",
    "프로필 사진 변경",
    "네이버ID 보안설정",
    "N Pay",
    "환경설정",
)


def surrogate_review_key(text: str, date: str | None = None, author: str | None = None) -> str:
    raw = f"{text}|{date or ''}|{author or ''}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _extract_rating(text: str) -> float | None:
    # simple pattern for values like 4.5 or 5점
    match = re.search(r"(\d(?:\.\d)?)\s*점", text)
    if match:
        return float(match.group(1))
    return None


def _is_portal_noise_text(text: str) -> bool:
    if not text:
        return False
    hits = sum(1 for marker in _PORTAL_NOISE_MARKERS if marker in text)
    return hits >= 2


def parse_reviews_html(html: str, fallback_reviews: list[str]) -> list[dict[str, Any]]:
    # Prefer crawler-extracted review blocks when available; they are more precise than
    # raw DOM-wide extraction from Naver shell pages.
    if fallback_reviews:
        dedup = list(dict.fromkeys([t for t in fallback_reviews if t and not _is_portal_noise_text(t)]))[:1000]
        parsed: list[dict[str, Any]] = []
        for raw in dedup:
            rating = _extract_rating(raw)
            parsed.append(
                {
                    "review_key": surrogate_review_key(raw),
                    "text": raw,
                    "date": None,
                    "author": None,
                    "rating": rating,
                    "is_ad_suspect": False,
                }
            )
        return parsed

    soup = BeautifulSoup(html, "html.parser")
    candidates: list[str] = []

    for node in soup.select("li, div, span, p"):
        text = node.get_text(" ", strip=True)
        if len(text) < 12:
            continue
        if any(noise in text for noise in ["더보기", "답글", "사장님", "접기"]):
            continue
        if _is_portal_noise_text(text):
            continue
        candidates.append(text)

    if not candidates:
        candidates = [t for t in fallback_reviews if not _is_portal_noise_text(t)]

    dedup = list(dict.fromkeys(candidates))[:1000]
    parsed: list[dict[str, Any]] = []
    for raw in dedup:
        rating = _extract_rating(raw)
        parsed.append(
            {
                "review_key": surrogate_review_key(raw),
                "text": raw,
                "date": None,
                "author": None,
                "rating": rating,
                "is_ad_suspect": False,
            }
        )
    return parsed


def to_jsonl(records: list[dict[str, Any]]) -> str:
    return "\n".join(json.dumps(rec, ensure_ascii=False) for rec in records)
