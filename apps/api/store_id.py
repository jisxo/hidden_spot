import re
from urllib.parse import urlparse

from libs.common.run_context import sha256_text


def extract_store_id_from_url(url: str) -> str | None:
    # Naver place IDs can be numeric or alpha-numeric tokens.
    place_match = re.search(r"/(?:entry/)?place/([A-Za-z0-9_-]+)", url)
    if place_match:
        return place_match.group(1)

    query_match = re.search(r"(?:query|q)=([^&]+)", url)
    if query_match:
        return query_match.group(1)[:64]

    parsed = urlparse(url)
    path_parts = [p for p in parsed.path.split("/") if p]
    if path_parts:
        tail = path_parts[-1]
        if tail:
            return tail[:64]
    return None


def derive_store_id(url: str) -> str:
    extracted = extract_store_id_from_url(url)
    if extracted:
        return extracted
    return f"tmp_{sha256_text(url)[:16]}"
