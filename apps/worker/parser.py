import hashlib
import json
import re
from datetime import datetime
from typing import Any

from bs4 import BeautifulSoup


def surrogate_review_key(text: str, date: str | None = None, author: str | None = None) -> str:
    raw = f"{text}|{date or ''}|{author or ''}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _extract_rating(text: str) -> float | None:
    # simple pattern for values like 4.5 or 5점
    match = re.search(r"(\d(?:\.\d)?)\s*점", text)
    if match:
        return float(match.group(1))
    return None


def parse_reviews_html(html: str, fallback_reviews: list[str]) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[str] = []

    for node in soup.select("li, div, span, p"):
        text = node.get_text(" ", strip=True)
        if len(text) < 12:
            continue
        if any(noise in text for noise in ["더보기", "답글", "사장님", "접기"]):
            continue
        candidates.append(text)

    if not candidates:
        candidates = fallback_reviews

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
