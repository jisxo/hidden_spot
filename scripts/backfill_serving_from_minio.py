#!/usr/bin/env python3
import argparse
import json
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill serving DB(stores/analysis/store_snapshots) from MinIO gold objects")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    db = ApiDatabase()
    minio = MinioDataLakeClient()
    gold_bucket = minio.gold_bucket
    gold_keys = minio.list_keys(gold_bucket, "gold/analysis/")

    upserted = 0
    skipped = 0
    failures = 0

    for key in gold_keys:
        try:
            payload = minio.get_json(gold_bucket, key)
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
            gold_path = f"s3://{gold_bucket}/{key}"

            if args.dry_run:
                upserted += 1
                continue

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
        except Exception as exc:
            failures += 1
            print(json.dumps({"key": key, "error": str(exc)}, ensure_ascii=False))

    result = {
        "ok": failures == 0,
        "gold_keys": len(gold_keys),
        "upserted": upserted,
        "skipped": skipped,
        "failures": failures,
        "dry_run": args.dry_run,
        "database_url_set": bool(os.getenv("DATABASE_URL")),
    }
    print(json.dumps(result, ensure_ascii=False))
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
