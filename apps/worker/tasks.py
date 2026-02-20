import asyncio
import time
from datetime import datetime

from apps.worker.crawler import NaverMapsCrawler
from apps.worker.db import WorkerDatabase
from libs.common import KeyParts, MinioDataLakeClient, sha256_bytes
from libs.common.object_keys import artifacts_hash_index, bronze_reviews_html_gz, bronze_store_meta


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
        return {"run_id": run_id, "status": "crawled", "bronze_path": crawl_result["bronze_meta_path"]}
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
