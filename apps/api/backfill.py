import os
from typing import Any

from apps.api.db import ApiDatabase
from libs.common import MinioDataLakeClient


def _safe_float(value: Any, default: float) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def backfill_serving_from_gold(
    *,
    db: ApiDatabase,
    minio: MinioDataLakeClient | None = None,
    max_items: int = 0,
) -> dict[str, Any]:
    """Backfill stores/analysis/snapshots from gold objects.

    max_items:
      - 0 means no limit.
      - positive number means process up to that many keys.
    """
    client = minio or MinioDataLakeClient()
    gold_bucket = client.gold_bucket
    gold_keys = client.list_keys(gold_bucket, "gold/analysis/")
    if max_items > 0:
        gold_keys = gold_keys[:max_items]

    upserted = 0
    skipped = 0
    failures = 0

    for key in gold_keys:
        try:
            payload = client.get_json(gold_bucket, key)
            if not isinstance(payload, dict):
                skipped += 1
                continue

            store_id = str(payload.get("store_id") or "").strip()
            run_id = str(payload.get("run_id") or "").strip()
            collected_at = str(payload.get("collected_at") or "").strip()
            analysis = payload.get("analysis") if isinstance(payload.get("analysis"), dict) else {}
            legacy = payload.get("legacy_source") if isinstance(payload.get("legacy_source"), dict) else {}

            if not store_id or not run_id or not collected_at:
                skipped += 1
                continue

            url = (
                str(legacy.get("original_url") or "").strip()
                or str(legacy.get("url") or "").strip()
                or f"https://map.naver.com/p/entry/place/{store_id}"
            )
            name = str(legacy.get("name") or "").strip() or None
            lat = _safe_float(legacy.get("latitude"), 37.5665)
            lng = _safe_float(legacy.get("longitude"), 126.9780)
            category = str(analysis.get("vibe") or "").strip() or None

            summary_3lines = str(analysis.get("summary_3lines") or "").strip()
            vibe = str(analysis.get("vibe") or "").strip()
            signature_menu_json = analysis.get("signature_menu") if isinstance(analysis.get("signature_menu"), list) else []
            tips_json = analysis.get("tips") if isinstance(analysis.get("tips"), list) else []
            score = _safe_float(analysis.get("score"), 0.0)
            ad_review_ratio = _safe_float(analysis.get("ad_review_ratio"), 0.0)
            review_summary_json = analysis.get("review_summary") if isinstance(analysis.get("review_summary"), dict) else {}
            categories_json = analysis.get("categories") if isinstance(analysis.get("categories"), list) else []
            gold_path = f"s3://{gold_bucket}/{key}"

            db.upsert_store(store_id=store_id, url=url, name=name, lat=lat, lng=lng, category=category)
            db.upsert_analysis(
                store_id=store_id,
                collected_at_iso=collected_at,
                run_id=run_id,
                summary_3lines=summary_3lines,
                vibe=vibe,
                signature_menu_json=signature_menu_json,
                tips_json=tips_json,
                score=score,
                ad_review_ratio=ad_review_ratio,
                review_summary_json=review_summary_json,
                categories_json=categories_json,
            )
            db.upsert_snapshot(
                store_id=store_id,
                collected_at_iso=collected_at,
                run_id=run_id,
                url=url,
                status="completed",
                progress=100,
                gold_path=gold_path,
            )
            upserted += 1
        except Exception:
            failures += 1

    return {
        "ok": failures == 0,
        "gold_keys": len(gold_keys),
        "upserted": upserted,
        "skipped": skipped,
        "failures": failures,
        "database_url_set": bool(os.getenv("DATABASE_URL")),
    }
