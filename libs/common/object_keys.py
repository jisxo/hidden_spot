from dataclasses import dataclass


@dataclass(frozen=True)
class KeyParts:
    store_id: str
    collected_at_iso: str
    run_id: str
    dt: str


def _require(parts: KeyParts) -> None:
    if not parts.store_id or not parts.collected_at_iso or not parts.run_id:
        raise ValueError("store_id, collected_at_iso, run_id are required")


def bronze_reviews_html_gz(parts: KeyParts) -> str:
    _require(parts)
    return (
        "bronze/naver_map/"
        f"store_id={parts.store_id}/collected_at={parts.collected_at_iso}/run_id={parts.run_id}/reviews.html.gz"
    )


def bronze_store_meta(parts: KeyParts) -> str:
    _require(parts)
    return (
        "bronze/naver_map/"
        f"store_id={parts.store_id}/collected_at={parts.collected_at_iso}/run_id={parts.run_id}/store_meta.json"
    )


def silver_reviews_jsonl(parts: KeyParts) -> str:
    _require(parts)
    return f"silver/reviews/store_id={parts.store_id}/dt={parts.dt}/run_id={parts.run_id}/reviews.jsonl"


def gold_analysis_json(parts: KeyParts) -> str:
    _require(parts)
    return f"gold/analysis/store_id={parts.store_id}/dt={parts.dt}/run_id={parts.run_id}/analysis.json"


def artifacts_chunk_map(parts: KeyParts) -> str:
    _require(parts)
    return f"artifacts/chunks/store_id={parts.store_id}/dt={parts.dt}/run_id={parts.run_id}/chunk_summaries.json"


def artifacts_hash_index(content_hash: str) -> str:
    return f"artifacts/hash_index/bronze_reviews/{content_hash}.json"


def artifacts_debug_blocked_png(parts: KeyParts) -> str:
    _require(parts)
    return f"artifacts/debug/store_id={parts.store_id}/dt={parts.dt}/run_id={parts.run_id}/blocked_suspected.png"


def artifacts_debug_final_failure_png(parts: KeyParts) -> str:
    _require(parts)
    return f"artifacts/debug/store_id={parts.store_id}/dt={parts.dt}/run_id={parts.run_id}/final_failure.png"
