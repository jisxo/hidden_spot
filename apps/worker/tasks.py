import asyncio
import json
import time
from datetime import datetime

from apps.worker.crawler import NaverMapsCrawler
from apps.worker.db import WorkerDatabase
from apps.worker.dq import DQError, validate_reviews
from apps.worker.llm import ChunkedAnalyzer
from apps.worker.parser import parse_reviews_html, to_jsonl
from libs.common import KeyParts, MinioDataLakeClient, sha256_bytes
from libs.common.object_keys import (
    artifacts_chunk_map,
    artifacts_hash_index,
    bronze_reviews_html_gz,
    bronze_store_meta,
    gold_analysis_json,
    silver_reviews_jsonl,
)


def _now_ms() -> int:
    return int(time.perf_counter() * 1000)


def process_job(run_id: str, store_id: str, url: str, collected_at_iso: str) -> dict:
    db = WorkerDatabase()
    minio = MinioDataLakeClient()

    collected_at = datetime.fromisoformat(collected_at_iso.replace("Z", "+00:00"))
    parts = KeyParts(store_id=store_id, collected_at_iso=collected_at_iso, run_id=run_id, dt=collected_at.strftime("%Y-%m-%d"))

    try:
        crawl_start = _now_ms()
        db.update_snapshot(run_id=run_id, status="crawling", progress=10)

        crawler = NaverMapsCrawler()
        crawl_result = process_crawl(crawler=crawler, minio=minio, parts=parts, run_id=run_id, url=url)

        duration = _now_ms() - crawl_start
        db.log_event(run_id=run_id, stage="crawl", status="ok", duration_ms=duration, payload={"review_count": crawl_result["review_count"]})
        db.update_snapshot(
            run_id=run_id,
            status="crawled",
            progress=35,
            bronze_path=crawl_result["bronze_meta_path"],
        )

        parse_start = _now_ms()
        db.update_snapshot(run_id=run_id, status="parsing", progress=45)
        parse_result = process_parse(minio=minio, parts=parts, run_id=run_id)
        parse_duration = _now_ms() - parse_start
        db.log_event(
            run_id=run_id,
            stage="parse",
            status="ok",
            duration_ms=parse_duration,
            payload={"review_count": parse_result["review_count"]},
        )
        db.update_snapshot(run_id=run_id, status="parsed", progress=65, silver_path=parse_result["silver_path"])

        llm_start = _now_ms()
        db.update_snapshot(run_id=run_id, status="analyzing", progress=75)
        llm_result = process_llm(minio=minio, db=db, parts=parts, run_id=run_id, collected_at_iso=collected_at_iso)
        llm_duration = _now_ms() - llm_start
        db.log_event(
            run_id=run_id,
            stage="llm",
            status="ok",
            duration_ms=llm_duration,
            payload={"chunk_count": llm_result["chunk_count"], "token_total": llm_result["tokens"]["total"]},
        )
        db.update_snapshot(run_id=run_id, status="completed", progress=100, gold_path=llm_result["gold_path"])

        return {
            "run_id": run_id,
            "status": "completed",
            "bronze_path": crawl_result["bronze_meta_path"],
            "silver_path": parse_result["silver_path"],
            "gold_path": llm_result["gold_path"],
        }
    except DQError as exc:
        db.log_event(run_id=run_id, stage="dq", status="failed", duration_ms=0, payload={"error": str(exc)})
        db.update_snapshot(run_id=run_id, status="failed", progress=100, error_reason=str(exc))
        raise
    except Exception as exc:
        db.log_event(run_id=run_id, stage="crawl", status="failed", duration_ms=0, payload={"error": str(exc)})
        db.update_snapshot(run_id=run_id, status="failed", progress=100, error_reason=str(exc))
        raise


def process_crawl(crawler: NaverMapsCrawler, minio: MinioDataLakeClient, parts: KeyParts, run_id: str, url: str) -> dict:
    data = asyncio.run(crawler.crawl(url=url))

    raw_html = data.get("raw_html", "")
    raw_html_bytes = raw_html.encode("utf-8")
    content_hash = sha256_bytes(raw_html_bytes)

    hash_key = artifacts_hash_index(content_hash)
    html_key = bronze_reviews_html_gz(parts)
    html_saved = False

    if not minio.object_exists(minio.artifacts_bucket, hash_key):
        minio.put_gzip_text(minio.bronze_bucket, html_key, raw_html)
        minio.put_json(minio.artifacts_bucket, hash_key, {"content_hash": content_hash, "first_seen_html_key": html_key})
        html_saved = True

    meta = {
        "run_id": run_id,
        "store_id": parts.store_id,
        "collected_at": parts.collected_at_iso,
        "source_url": url,
        "final_url": data.get("final_url"),
        "naver_place_id": data.get("naver_place_id"),
        "name": data.get("name"),
        "address": data.get("address"),
        "review_count": data.get("review_count", 0),
        "reviews": data.get("reviews", []),
        "content_hash": content_hash,
        "html_key": html_key,
        "html_saved": html_saved,
    }

    meta_key = bronze_store_meta(parts)
    minio.put_json(minio.bronze_bucket, meta_key, meta)

    return {
        "review_count": int(data.get("review_count", 0)),
        "bronze_meta_path": f"s3://{minio.bronze_bucket}/{meta_key}",
        "bronze_html_path": f"s3://{minio.bronze_bucket}/{html_key}",
    }


def process_parse(minio: MinioDataLakeClient, parts: KeyParts, run_id: str) -> dict:
    meta_key = bronze_store_meta(parts)
    meta = minio.get_json(minio.bronze_bucket, meta_key)

    html_key = meta.get("html_key")
    html = ""
    if meta.get("html_saved", False) and html_key:
        html = minio.get_gzip_text(minio.bronze_bucket, html_key)
    else:
        hash_key = artifacts_hash_index(meta["content_hash"])
        hash_meta = minio.get_json(minio.artifacts_bucket, hash_key)
        first_seen = hash_meta["first_seen_html_key"]
        html = minio.get_gzip_text(minio.bronze_bucket, first_seen)

    parsed_reviews = parse_reviews_html(html=html, fallback_reviews=meta.get("reviews", []))
    validate_reviews(parsed_reviews, store_id=parts.store_id, collected_at=parts.collected_at_iso)

    silver_key = silver_reviews_jsonl(parts)
    minio.put_bytes(
        minio.silver_bucket,
        silver_key,
        to_jsonl(parsed_reviews).encode("utf-8"),
        content_type="application/x-ndjson",
    )

    return {
        "run_id": run_id,
        "review_count": len(parsed_reviews),
        "silver_path": f"s3://{minio.silver_bucket}/{silver_key}",
    }


def process_llm(minio: MinioDataLakeClient, db: WorkerDatabase, parts: KeyParts, run_id: str, collected_at_iso: str) -> dict:
    analyzer = ChunkedAnalyzer()
    silver_key = silver_reviews_jsonl(parts)
    jsonl_text = minio.get_bytes(minio.silver_bucket, silver_key).decode("utf-8")
    reviews = []
    for line in jsonl_text.splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if rec.get("text"):
            reviews.append(rec["text"])

    analysis = analyzer.analyze(reviews=reviews)
    final = analysis["result"]

    chunk_key = artifacts_chunk_map(parts)
    minio.put_json(minio.artifacts_bucket, chunk_key, analysis["chunk_summaries"])

    gold_payload = {
        "run_id": run_id,
        "collected_at": collected_at_iso,
        "store_id": parts.store_id,
        "crawler_version": "v1",
        "parser_version": "v1",
        "llm_model": analysis["llm_model"],
        "prompt_version": analysis["prompt_version"],
        "prompt_hash": analysis["prompt_hash"],
        "input_snapshot_path": f"s3://{minio.silver_bucket}/{silver_key}",
        "cost": None,
        "tokens": analysis["tokens"],
        "chunk_count": analysis["chunk_count"],
        "analysis": {
            "summary_3lines": final.get("summary_3lines", ""),
            "vibe": final.get("vibe", ""),
            "signature_menu": final.get("signature_menu", []),
            "tips": final.get("tips", []),
            "score": final.get("score", 0),
            "ad_review_ratio": final.get("ad_review_ratio", 0.0),
        },
    }

    gold_key = gold_analysis_json(parts)
    minio.put_json(minio.gold_bucket, gold_key, gold_payload)

    db.upsert_analysis(
        store_id=parts.store_id,
        collected_at=collected_at_iso,
        run_id=run_id,
        summary_3lines=gold_payload["analysis"]["summary_3lines"],
        vibe=gold_payload["analysis"]["vibe"],
        signature_menu=gold_payload["analysis"]["signature_menu"],
        tips=gold_payload["analysis"]["tips"],
        score=float(gold_payload["analysis"]["score"]),
        ad_review_ratio=float(gold_payload["analysis"]["ad_review_ratio"]),
    )

    return {"gold_path": f"s3://{minio.gold_bucket}/{gold_key}", "chunk_count": analysis["chunk_count"], "tokens": analysis["tokens"]}
