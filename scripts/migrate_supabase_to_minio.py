#!/usr/bin/env python3
import argparse
import hashlib
import html
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.common import KeyParts, MinioDataLakeClient
from libs.common.object_keys import (
    artifacts_chunk_map,
    artifacts_hash_index,
    bronze_reviews_html_gz,
    bronze_store_meta,
    gold_analysis_json,
    silver_reviews_jsonl,
)


def _parse_iso(ts: str | None) -> datetime:
    if not ts:
        return datetime.now(timezone.utc)
    value = ts.strip()
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _isoformat_z(ts: datetime) -> str:
    return ts.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return _isoformat_z(value)
    return str(value)


def _to_slug(value: str | None) -> str:
    if not value:
        return ""
    return "".join(ch if ch.isalnum() else "-" for ch in value).strip("-").lower()


def _pick_store_id(row: dict[str, Any]) -> str:
    place_id = str(row.get("naver_place_id") or "").strip()
    if place_id:
        return place_id[:64]
    original_url = str(row.get("original_url") or "").strip()
    if original_url:
        digest = hashlib.sha256(original_url.encode("utf-8")).hexdigest()[:16]
        return f"url_{digest}"
    row_id = str(row.get("id") or "").strip()
    if row_id:
        return f"legacy_{row_id.replace('-', '')[:24]}"
    return f"legacy_{hashlib.sha256(json.dumps(row, ensure_ascii=False, default=_json_default).encode('utf-8')).hexdigest()[:24]}"


def _pick_run_id(row: dict[str, Any]) -> str:
    row_id = str(row.get("id") or "").strip()
    if row_id:
        return f"legacy-{row_id}"
    base = f"{row.get('original_url', '')}|{row.get('created_at', '')}|{row.get('name', '')}"
    return f"legacy-{hashlib.sha256(base.encode('utf-8')).hexdigest()[:32]}"


def _normalize_reviews(raw_reviews: Any) -> list[str]:
    if not raw_reviews:
        return []
    if isinstance(raw_reviews, list):
        out = []
        for item in raw_reviews:
            text = str(item or "").strip()
            if text:
                out.append(text)
        return out
    text = str(raw_reviews).strip()
    return [text] if text else []


def _render_reviews_html(store_name: str, reviews: list[str]) -> str:
    safe_name = html.escape(store_name or "legacy-store")
    lines = [
        "<!doctype html>",
        '<html lang="ko"><head><meta charset="utf-8"><title>Legacy Reviews</title></head><body>',
        f"<h1>{safe_name}</h1>",
        "<ul>",
    ]
    for review in reviews:
        lines.append(f"<li>{html.escape(review)}</li>")
    lines.extend(["</ul>", "</body></html>"])
    return "\n".join(lines)


def _review_jsonl(reviews: list[str]) -> bytes:
    lines = []
    for idx, text in enumerate(reviews):
        payload = {
            "review_key": f"legacy-{idx+1:04d}",
            "date": None,
            "rating": None,
            "text": text,
            "is_ad_suspect": False,
        }
        lines.append(json.dumps(payload, ensure_ascii=False))
    return ("\n".join(lines) + ("\n" if lines else "")).encode("utf-8")


def _gold_payload(
    *,
    row: dict[str, Any],
    run_id: str,
    store_id: str,
    collected_at_iso: str,
    input_snapshot_path: str,
) -> dict[str, Any]:
    summary_json = row.get("summary_json") or {}
    if not isinstance(summary_json, dict):
        summary_json = {}

    one_line = str(summary_json.get("one_line_copy") or "").strip()
    tags = summary_json.get("tags") if isinstance(summary_json.get("tags"), list) else []
    vibe = str((summary_json.get("taste_profile") or {}).get("category_name") or "").strip()
    if not vibe and tags:
        vibe = ", ".join(str(t) for t in tags[:3] if t)
    signature_menu = row.get("must_eat_menus") if isinstance(row.get("must_eat_menus"), list) else []
    tips = summary_json.get("pro_tips") if isinstance(summary_json.get("pro_tips"), list) else []

    prompt_basis = json.dumps(
        {
            "name": row.get("name"),
            "summary_json": summary_json,
            "must_eat_menus": signature_menu,
            "search_tags": row.get("search_tags"),
        },
        ensure_ascii=False,
    )
    prompt_hash = hashlib.sha256(prompt_basis.encode("utf-8")).hexdigest()

    return {
        "run_id": run_id,
        "collected_at": collected_at_iso,
        "store_id": store_id,
        "crawler_version": "legacy_supabase_v1",
        "parser_version": "legacy_supabase_v1",
        "llm_model": "legacy-import",
        "prompt_version": "legacy-import-v1",
        "prompt_hash": prompt_hash,
        "input_snapshot_path": input_snapshot_path,
        "cost": None,
        "tokens": {"prompt": 0, "completion": 0, "total": 0},
        "chunk_count": 0,
        "analysis": {
            "summary_3lines": one_line,
            "vibe": vibe,
            "signature_menu": [str(x) for x in signature_menu if str(x).strip()],
            "tips": [str(x) for x in tips if str(x).strip()],
            "score": float(row.get("ai_score") or 0),
            "ad_review_ratio": 0.0,
        },
        "legacy_source": {
            "restaurant_id": row.get("id"),
            "name": row.get("name"),
            "address": row.get("address"),
            "latitude": row.get("latitude"),
            "longitude": row.get("longitude"),
            "transport_info": row.get("transport_info"),
            "search_tags": row.get("search_tags") if isinstance(row.get("search_tags"), list) else [],
        },
    }


def _fetch_supabase_rows(base_url: str, api_key: str, page_size: int = 500) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        params = urlencode({"select": "*", "order": "created_at.asc", "limit": page_size, "offset": offset})
        url = f"{base_url.rstrip('/')}/rest/v1/restaurants?{params}"
        req = Request(
            url,
            headers={
                "apikey": api_key,
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json",
            },
            method="GET",
        )
        with urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        if not payload:
            break
        rows.extend(payload)
        if len(payload) < page_size:
            break
        offset += page_size
    return rows


def _load_rows_from_file(file_path: Path) -> list[dict[str, Any]]:
    data = json.loads(file_path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"Expected list JSON in {file_path}, got {type(data).__name__}")
    rows = []
    for item in data:
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _write_legacy_rows_to_minio(
    *,
    minio: MinioDataLakeClient,
    rows: list[dict[str, Any]],
    overwrite: bool,
    dry_run: bool,
) -> dict[str, Any]:
    written = 0
    skipped = 0
    details: list[dict[str, Any]] = []

    for row in rows:
        store_id = _pick_store_id(row)
        run_id = _pick_run_id(row)
        ts = _parse_iso(str(row.get("created_at") or ""))
        collected_at_iso = _isoformat_z(ts)
        dt = ts.strftime("%Y-%m-%d")
        parts = KeyParts(store_id=store_id, collected_at_iso=collected_at_iso, run_id=run_id, dt=dt)

        reviews = _normalize_reviews(row.get("raw_reviews"))
        html_text = _render_reviews_html(str(row.get("name") or ""), reviews)
        content_hash = hashlib.sha256(html_text.encode("utf-8")).hexdigest()

        html_key = bronze_reviews_html_gz(parts)
        meta_key = bronze_store_meta(parts)
        silver_key = silver_reviews_jsonl(parts)
        gold_key = gold_analysis_json(parts)
        chunk_key = artifacts_chunk_map(parts)
        hash_key = artifacts_hash_index(content_hash)

        silver_path = f"s3://{minio.silver_bucket}/{silver_key}"
        gold_payload = _gold_payload(
            row=row,
            run_id=run_id,
            store_id=store_id,
            collected_at_iso=collected_at_iso,
            input_snapshot_path=silver_path,
        )

        bronze_meta = {
            "run_id": run_id,
            "store_id": store_id,
            "collected_at": collected_at_iso,
            "source_url": row.get("original_url"),
            "final_url": row.get("original_url"),
            "naver_place_id": row.get("naver_place_id"),
            "name": row.get("name"),
            "address": row.get("address"),
            "review_count": len(reviews),
            "reviews": reviews,
            "content_hash": content_hash,
            "html_key": html_key,
            "html_saved": True,
            "legacy_import": True,
        }

        already_exists = minio.object_exists(minio.gold_bucket, gold_key)
        if already_exists and not overwrite:
            skipped += 1
            details.append({"store_id": store_id, "run_id": run_id, "status": "skipped_exists"})
            continue

        if not dry_run:
            if not minio.object_exists(minio.artifacts_bucket, hash_key):
                minio.put_gzip_text(minio.bronze_bucket, html_key, html_text)
                minio.put_json(
                    minio.artifacts_bucket,
                    hash_key,
                    {"content_hash": content_hash, "first_seen_html_key": html_key},
                )
            minio.put_json(minio.bronze_bucket, meta_key, bronze_meta)
            minio.put_bytes(
                minio.silver_bucket,
                silver_key,
                _review_jsonl(reviews),
                content_type="application/x-ndjson",
            )
            minio.put_json(minio.gold_bucket, gold_key, gold_payload)
            minio.put_json(
                minio.artifacts_bucket,
                chunk_key,
                {"legacy_summary": {"tags": (row.get("summary_json") or {}).get("tags", []), "slug": _to_slug(str(row.get("name") or ""))}},
            )

        written += 1
        details.append(
            {
                "store_id": store_id,
                "run_id": run_id,
                "status": "written" if not dry_run else "dry_run",
                "review_count": len(reviews),
                "gold_key": gold_key,
            }
        )

    return {"written": written, "skipped": skipped, "total": len(rows), "details": details}


def _ensure_buckets(minio: MinioDataLakeClient) -> None:
    for bucket in [minio.bronze_bucket, minio.silver_bucket, minio.gold_bucket, minio.artifacts_bucket]:
        if not minio.client.bucket_exists(bucket):
            minio.client.make_bucket(bucket)


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate legacy Supabase restaurants to MinIO Bronze/Silver/Gold.")
    parser.add_argument("--source", choices=["auto", "supabase", "file"], default="auto")
    parser.add_argument("--file", default="frontend/src/data/restaurants.json")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--report", default="testsprite_tests/tmp/supabase_to_minio_report.json")
    args = parser.parse_args()

    source_used = ""
    rows: list[dict[str, Any]] = []
    supabase_error: str | None = None

    if args.source in {"auto", "supabase"}:
        import os

        base_url = os.getenv("SUPABASE_URL", "").strip()
        api_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        if base_url and api_key:
            try:
                rows = _fetch_supabase_rows(base_url=base_url, api_key=api_key)
                source_used = "supabase"
            except (URLError, HTTPError, TimeoutError, OSError, json.JSONDecodeError) as exc:
                supabase_error = str(exc)
        else:
            supabase_error = "SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY missing"

    if not rows and args.source in {"auto", "file"}:
        file_path = Path(args.file)
        if file_path.exists():
            rows = _load_rows_from_file(file_path)
            source_used = f"file:{file_path}"

    if not rows:
        print(json.dumps({"ok": False, "error": "no source rows", "supabase_error": supabase_error}, ensure_ascii=False))
        return 1

    minio = MinioDataLakeClient()
    _ensure_buckets(minio)

    result = _write_legacy_rows_to_minio(
        minio=minio,
        rows=rows,
        overwrite=args.overwrite,
        dry_run=args.dry_run,
    )
    report = {
        "ok": True,
        "source": source_used,
        "supabase_error": supabase_error,
        "dry_run": args.dry_run,
        "overwrite": args.overwrite,
        "summary": {k: result[k] for k in ["total", "written", "skipped"]},
    }
    print(json.dumps(report, ensure_ascii=False))

    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(
            {
                **report,
                "details": result["details"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
