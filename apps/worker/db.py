import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone

import psycopg2
import psycopg2.extras


class WorkerDatabase:
    def __init__(self) -> None:
        self.database_url = os.getenv("DATABASE_URL", "postgresql://hidden_spot:hidden_spot@localhost:5432/hidden_spot")
        self.ensure_columns()

    @contextmanager
    def conn(self):
        conn = psycopg2.connect(self.database_url)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def update_snapshot(
        self,
        run_id: str,
        status: str,
        progress: int,
        bronze_path: str | None = None,
        silver_path: str | None = None,
        gold_path: str | None = None,
        error_reason: str | None = None,
        error_type: str | None = None,
        error_stage: str | None = None,
        evidence_paths_json: list[str] | None = None,
    ) -> None:
        sql = """
        UPDATE store_snapshots
        SET status=%s,
            progress=%s,
            bronze_path=COALESCE(%s, bronze_path),
            silver_path=COALESCE(%s, silver_path),
            gold_path=COALESCE(%s, gold_path),
            error_reason=%s,
            error_type=%s,
            error_stage=%s,
            evidence_paths_json=COALESCE(%s::jsonb, '[]'::jsonb),
            updated_at=NOW()
        WHERE run_id=%s;
        """
        with self.conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql,
                    (
                        status,
                        progress,
                        bronze_path,
                        silver_path,
                        gold_path,
                        error_reason,
                        error_type,
                        error_stage,
                        json.dumps(evidence_paths_json) if evidence_paths_json is not None else None,
                        run_id,
                    ),
                )

    def get_snapshot(self, run_id: str):
        with self.conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM store_snapshots WHERE run_id=%s", (run_id,))
                return cur.fetchone()

    def log_event(self, run_id: str, stage: str, status: str, duration_ms: int, payload: dict | None = None) -> None:
        event = {
            "run_id": run_id,
            "stage": stage,
            "status": status,
            "duration_ms": duration_ms,
            "payload": payload or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        print(json.dumps(event, ensure_ascii=False))

    def ensure_columns(self) -> None:
        sql = """
        DO $$
        BEGIN
            IF to_regclass('public.stores') IS NOT NULL THEN
                ALTER TABLE stores ADD COLUMN IF NOT EXISTS naver_place_id TEXT;
            END IF;
            IF to_regclass('public.analysis') IS NOT NULL THEN
                ALTER TABLE analysis ADD COLUMN IF NOT EXISTS review_summary_json JSONB;
                ALTER TABLE analysis ADD COLUMN IF NOT EXISTS categories_json JSONB;
            END IF;
            IF to_regclass('public.store_snapshots') IS NOT NULL THEN
                ALTER TABLE store_snapshots ADD COLUMN IF NOT EXISTS error_type TEXT;
                ALTER TABLE store_snapshots ADD COLUMN IF NOT EXISTS error_stage TEXT;
                ALTER TABLE store_snapshots ADD COLUMN IF NOT EXISTS evidence_paths_json JSONB NOT NULL DEFAULT '[]'::jsonb;
            END IF;
        END $$;
        """
        with self.conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)

    def upsert_store(
        self,
        *,
        store_id: str,
        url: str,
        naver_place_id: str | None = None,
        name: str | None = None,
        address: str | None = None,
        transport_info: str | None = None,
        lat: float | None = None,
        lng: float | None = None,
        category: str | None = None,
    ) -> None:
        sql = """
        INSERT INTO stores (store_id, url, naver_place_id, name, address, transport_info, lat, lng, category)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (store_id)
        DO UPDATE SET
            url = EXCLUDED.url,
            naver_place_id = COALESCE(NULLIF(EXCLUDED.naver_place_id, ''), stores.naver_place_id),
            name = COALESCE(NULLIF(EXCLUDED.name, ''), stores.name),
            address = COALESCE(NULLIF(EXCLUDED.address, ''), stores.address),
            transport_info = COALESCE(NULLIF(EXCLUDED.transport_info, ''), stores.transport_info),
            lat = COALESCE(EXCLUDED.lat, stores.lat),
            lng = COALESCE(EXCLUDED.lng, stores.lng),
            category = COALESCE(EXCLUDED.category, stores.category),
            updated_at = NOW();
        """
        with self.conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (store_id, url, naver_place_id, name, address, transport_info, lat, lng, category))

    def upsert_analysis(
        self,
        store_id: str,
        collected_at: str,
        run_id: str,
        summary_3lines: str,
        vibe: str,
        signature_menu: list,
        tips: list,
        score: float,
        ad_review_ratio: float,
        review_summary: dict | None = None,
        categories: list | None = None,
    ) -> None:
        sql = """
        INSERT INTO analysis
            (
                store_id, collected_at, run_id, summary_3lines, vibe,
                signature_menu_json, tips_json, score, ad_review_ratio,
                review_summary_json, categories_json, updated_at
            )
        VALUES
            (%s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s, %s::jsonb, %s::jsonb, NOW())
        ON CONFLICT (run_id)
        DO UPDATE SET
            summary_3lines = EXCLUDED.summary_3lines,
            vibe = EXCLUDED.vibe,
            signature_menu_json = EXCLUDED.signature_menu_json,
            tips_json = EXCLUDED.tips_json,
            score = EXCLUDED.score,
            ad_review_ratio = EXCLUDED.ad_review_ratio,
            review_summary_json = EXCLUDED.review_summary_json,
            categories_json = EXCLUDED.categories_json,
            updated_at = NOW();
        """
        with self.conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql,
                    (
                        store_id,
                        collected_at,
                        run_id,
                        summary_3lines,
                        vibe,
                        json.dumps(signature_menu, ensure_ascii=False),
                        json.dumps(tips, ensure_ascii=False),
                        score,
                        ad_review_ratio,
                        json.dumps(review_summary or {}, ensure_ascii=False),
                        json.dumps(categories or [], ensure_ascii=False),
                    ),
                )

    def upsert_embedding(self, store_id: str, doc_type: str, vector: list[float]) -> None:
        vector_literal = "[" + ",".join(f"{v:.8f}" for v in vector) + "]"
        sql = """
        INSERT INTO embeddings (store_id, doc_type, vector, updated_at)
        VALUES (%s, %s, %s::vector, NOW())
        ON CONFLICT (store_id, doc_type)
        DO UPDATE SET vector = EXCLUDED.vector, updated_at = NOW();
        """
        with self.conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (store_id, doc_type, vector_literal))

    def upsert_reviews(self, store_id: str, reviews: list[dict]) -> None:
        if not reviews:
            return
        sql = """
        INSERT INTO reviews (store_id, review_key, date, rating, text, is_ad_suspect, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, NOW())
        ON CONFLICT (store_id, review_key)
        DO UPDATE SET
            date = EXCLUDED.date,
            rating = EXCLUDED.rating,
            text = EXCLUDED.text,
            is_ad_suspect = EXCLUDED.is_ad_suspect;
        """
        values = []
        for review in reviews:
            values.append(
                (
                    store_id,
                    str(review.get("review_key") or ""),
                    review.get("date"),
                    review.get("rating"),
                    str(review.get("text") or ""),
                    bool(review.get("is_ad_suspect") or False),
                )
            )
        with self.conn() as conn:
            with conn.cursor() as cur:
                psycopg2.extras.execute_batch(cur, sql, values, page_size=200)
