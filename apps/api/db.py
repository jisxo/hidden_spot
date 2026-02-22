import os
import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import psycopg2
import psycopg2.extras


class ApiDatabase:
    def __init__(self) -> None:
        self.database_url = os.getenv("DATABASE_URL", "postgresql://hidden_spot:hidden_spot@localhost:5432/hidden_spot")
        self._legacy_by_store = self._load_legacy_index()

    def _load_legacy_index(self) -> dict[str, dict[str, Any]]:
        try:
            root = Path(__file__).resolve().parents[2]
            path = root / "frontend/src/data/restaurants.json"
            if not path.exists():
                return {}
            rows = json.loads(path.read_text(encoding="utf-8"))
            out: dict[str, dict[str, Any]] = {}
            for row in rows:
                key = str(row.get("naver_place_id") or row.get("id") or "").strip()
                if not key:
                    continue
                out[key] = row
            return out
        except Exception:
            return {}

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

    def ensure_tables(self) -> None:
        sql = """
        CREATE EXTENSION IF NOT EXISTS vector;

        CREATE TABLE IF NOT EXISTS stores (
            store_id TEXT PRIMARY KEY,
            url TEXT NOT NULL,
            naver_place_id TEXT,
            name TEXT,
            address TEXT,
            transport_info TEXT,
            lat DOUBLE PRECISION,
            lng DOUBLE PRECISION,
            category TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS store_snapshots (
            store_id TEXT NOT NULL,
            collected_at TIMESTAMPTZ NOT NULL,
            run_id TEXT PRIMARY KEY,
            url TEXT NOT NULL,
            bronze_path TEXT,
            silver_path TEXT,
            gold_path TEXT,
            status TEXT NOT NULL,
            progress INT NOT NULL DEFAULT 0,
            error_reason TEXT,
            error_type TEXT,
            error_stage TEXT,
            evidence_paths_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS analysis (
            store_id TEXT NOT NULL,
            collected_at TIMESTAMPTZ NOT NULL,
            run_id TEXT PRIMARY KEY,
            summary_3lines TEXT,
            vibe TEXT,
            signature_menu_json JSONB,
            tips_json JSONB,
            score DOUBLE PRECISION,
            ad_review_ratio DOUBLE PRECISION,
            review_summary_json JSONB,
            categories_json JSONB,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS embeddings (
            store_id TEXT NOT NULL,
            doc_type TEXT NOT NULL,
            vector vector(1536),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (store_id, doc_type)
        );

        CREATE TABLE IF NOT EXISTS reviews (
            store_id TEXT NOT NULL,
            review_key TEXT NOT NULL,
            date DATE,
            rating DOUBLE PRECISION,
            text TEXT NOT NULL,
            is_ad_suspect BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (store_id, review_key)
        );

        CREATE INDEX IF NOT EXISTS idx_store_snapshots_status ON store_snapshots(status);

        ALTER TABLE stores ADD COLUMN IF NOT EXISTS address TEXT;
        ALTER TABLE stores ADD COLUMN IF NOT EXISTS transport_info TEXT;
        ALTER TABLE stores ADD COLUMN IF NOT EXISTS naver_place_id TEXT;
        ALTER TABLE analysis ADD COLUMN IF NOT EXISTS review_summary_json JSONB;
        ALTER TABLE analysis ADD COLUMN IF NOT EXISTS categories_json JSONB;
        ALTER TABLE store_snapshots ADD COLUMN IF NOT EXISTS error_type TEXT;
        ALTER TABLE store_snapshots ADD COLUMN IF NOT EXISTS error_stage TEXT;
        ALTER TABLE store_snapshots ADD COLUMN IF NOT EXISTS evidence_paths_json JSONB NOT NULL DEFAULT '[]'::jsonb;
        """
        with self.conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)

    def upsert_store(
        self,
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
            name = COALESCE(EXCLUDED.name, stores.name),
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

    def create_snapshot(self, store_id: str, collected_at_iso: str, run_id: str, url: str, status: str) -> None:
        sql = """
        INSERT INTO store_snapshots (store_id, collected_at, run_id, url, status, progress)
        VALUES (%s, %s, %s, %s, %s, %s);
        """
        with self.conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (store_id, collected_at_iso, run_id, url, status, 0))

    def upsert_snapshot(
        self,
        *,
        store_id: str,
        collected_at_iso: str,
        run_id: str,
        url: str,
        status: str,
        progress: int = 0,
        bronze_path: str | None = None,
        silver_path: str | None = None,
        gold_path: str | None = None,
        error_reason: str | None = None,
        error_type: str | None = None,
        error_stage: str | None = None,
        evidence_paths_json: list[str] | None = None,
    ) -> None:
        sql = """
        INSERT INTO store_snapshots (
            store_id, collected_at, run_id, url, bronze_path, silver_path, gold_path, status, progress, error_reason,
            error_type, error_stage, evidence_paths_json
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, COALESCE(%s::jsonb, '[]'::jsonb))
        ON CONFLICT (run_id)
        DO UPDATE SET
            store_id = EXCLUDED.store_id,
            collected_at = EXCLUDED.collected_at,
            url = EXCLUDED.url,
            bronze_path = EXCLUDED.bronze_path,
            silver_path = EXCLUDED.silver_path,
            gold_path = EXCLUDED.gold_path,
            status = EXCLUDED.status,
            progress = EXCLUDED.progress,
            error_reason = EXCLUDED.error_reason,
            error_type = EXCLUDED.error_type,
            error_stage = EXCLUDED.error_stage,
            evidence_paths_json = EXCLUDED.evidence_paths_json,
            updated_at = NOW();
        """
        with self.conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql,
                    (
                        store_id,
                        collected_at_iso,
                        run_id,
                        url,
                        bronze_path,
                        silver_path,
                        gold_path,
                        status,
                        progress,
                        error_reason,
                        error_type,
                        error_stage,
                        json.dumps(evidence_paths_json) if evidence_paths_json is not None else None,
                    ),
                )

    def get_snapshot(self, run_id: str):
        with self.conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM store_snapshots WHERE run_id = %s", (run_id,))
                return cur.fetchone()

    def smart_search(self, terms: list[str], limit: int = 20):
        pattern_terms = [f"%{t}%" for t in terms if t]
        where_clauses = []
        params = []
        for _ in pattern_terms:
            where_clauses.append(
                "(COALESCE(a.summary_3lines, '') ILIKE %s OR COALESCE(a.vibe, '') ILIKE %s OR COALESCE(s.name, '') ILIKE %s)"
            )
        for p in pattern_terms:
            params.extend([p, p, p])

        where_sql = " OR ".join(where_clauses) if where_clauses else "TRUE"
        sql = f"""
        SELECT
            s.store_id,
            s.url,
            s.name,
            s.address,
            s.transport_info,
            s.lat,
            s.lng,
            a.summary_3lines,
            a.vibe,
            a.signature_menu_json,
            a.score,
            a.ad_review_ratio,
            a.updated_at
        FROM analysis a
        JOIN stores s ON s.store_id = a.store_id
        WHERE {where_sql}
        ORDER BY a.updated_at DESC
        LIMIT %s;
        """
        params.append(limit)

        with self.conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, tuple(params))
                rows = cur.fetchall()
        return [row for row in rows if not self._is_low_quality_projection(row)]

    def upsert_analysis(
        self,
        *,
        store_id: str,
        collected_at_iso: str,
        run_id: str,
        summary_3lines: str,
        vibe: str,
        signature_menu_json: list[Any] | None,
        tips_json: list[Any] | None,
        score: float,
        ad_review_ratio: float,
        review_summary_json: dict[str, Any] | None = None,
        categories_json: list[Any] | None = None,
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
            store_id = EXCLUDED.store_id,
            collected_at = EXCLUDED.collected_at,
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
                        collected_at_iso,
                        run_id,
                        summary_3lines,
                        vibe,
                        psycopg2.extras.Json(signature_menu_json or []),
                        psycopg2.extras.Json(tips_json or []),
                        score,
                        ad_review_ratio,
                        psycopg2.extras.Json(review_summary_json or {}),
                        psycopg2.extras.Json(categories_json or []),
                    ),
                )

    def get_store(self, store_id: str):
        with self.conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM stores WHERE store_id = %s", (store_id,))
                return cur.fetchone()

    def delete_store_cascade(self, store_id: str) -> int:
        with self.conn() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM analysis WHERE store_id = %s", (store_id,))
                deleted = cur.rowcount
                cur.execute("DELETE FROM store_snapshots WHERE store_id = %s", (store_id,))
                cur.execute("DELETE FROM stores WHERE store_id = %s", (store_id,))
                deleted += cur.rowcount
        return deleted

    def list_restaurants(self, *, min_score: int = 0, keyword: str | None = None):
        sql = """
        WITH latest AS (
            SELECT DISTINCT ON (a.store_id)
                a.store_id,
                a.run_id,
                a.collected_at,
                a.summary_3lines,
                a.vibe,
                a.signature_menu_json,
                a.tips_json,
                a.review_summary_json,
                a.categories_json,
                a.score,
                a.ad_review_ratio,
                s.url,
                s.naver_place_id,
                s.name,
                s.address,
                s.transport_info,
                (
                    SELECT COALESCE(jsonb_agg(rv.text), '[]'::jsonb)
                    FROM (
                        SELECT r.text
                        FROM reviews r
                        WHERE r.store_id = a.store_id
                        ORDER BY r.created_at DESC
                        LIMIT 100
                    ) rv
                ) AS raw_reviews_json,
                s.lat,
                s.lng,
                s.category,
                a.updated_at
            FROM analysis a
            JOIN stores s ON s.store_id = a.store_id
            ORDER BY a.store_id, a.updated_at DESC
        )
        SELECT *
        FROM latest
        WHERE score >= %s
          AND (
            %s IS NULL
            OR COALESCE(name, '') ILIKE %s
            OR COALESCE(vibe, '') ILIKE %s
            OR COALESCE(summary_3lines, '') ILIKE %s
            OR COALESCE(url, '') ILIKE %s
            OR COALESCE(signature_menu_json::text, '') ILIKE %s
          )
        ORDER BY updated_at DESC;
        """
        term = None
        like = None
        if keyword and keyword.strip():
            term = keyword.strip()
            like = f"%{term}%"

        with self.conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, (min_score, term, like, like, like, like, like))
                rows = cur.fetchall()
        filtered_rows = [row for row in rows if not self._is_low_quality_projection(row)]
        return [self._to_restaurant_shape(row) for row in filtered_rows]

    def get_restaurant(self, store_id: str):
        sql = """
        WITH latest AS (
            SELECT DISTINCT ON (a.store_id)
                a.store_id,
                a.run_id,
                a.collected_at,
                a.summary_3lines,
                a.vibe,
                a.signature_menu_json,
                a.tips_json,
                a.review_summary_json,
                a.categories_json,
                a.score,
                a.ad_review_ratio,
                s.url,
                s.naver_place_id,
                s.name,
                s.address,
                s.transport_info,
                (
                    SELECT COALESCE(jsonb_agg(rv.text), '[]'::jsonb)
                    FROM (
                        SELECT r.text
                        FROM reviews r
                        WHERE r.store_id = a.store_id
                        ORDER BY r.created_at DESC
                        LIMIT 100
                    ) rv
                ) AS raw_reviews_json,
                s.lat,
                s.lng,
                s.category,
                a.updated_at
            FROM analysis a
            JOIN stores s ON s.store_id = a.store_id
            WHERE a.store_id = %s
            ORDER BY a.store_id, a.updated_at DESC
        )
        SELECT * FROM latest;
        """
        with self.conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, (store_id,))
                row = cur.fetchone()
        if not row or self._is_low_quality_projection(row):
            return None
        return self._to_restaurant_shape(row)

    def _contains_portal_boilerplate(self, text: str) -> bool:
        if not text:
            return False
        markers = (
            "본문 바로가기",
            "주 메뉴 바로가기",
            "내정보 보기",
            "프로필 사진 변경",
            "네이버ID 보안설정",
            "N Pay",
            "환경설정",
        )
        hits = sum(1 for marker in markers if marker in text)
        return hits >= 2

    def _is_low_quality_projection(self, row: dict[str, Any]) -> bool:
        store_id = str(row.get("store_id") or "").strip()
        name = str(row.get("name") or "").strip()
        summary = str(row.get("summary_3lines") or "").strip()
        signature_menu = row.get("signature_menu_json") or []
        has_menu = isinstance(signature_menu, list) and any(str(item).strip() for item in signature_menu)
        has_summary = bool(summary) and not self._contains_portal_boilerplate(summary)

        # Some map pages hide/store the place title late in the DOM. Keep rows that still
        # have meaningful analysis/menu even when name is missing.
        if not name and not (has_menu or has_summary):
            return True
        if store_id and name.lower() == store_id.lower() and not (has_menu or has_summary):
            return True
        if self._contains_portal_boilerplate(summary) and not has_menu:
            return True
        return False

    def _to_restaurant_shape(self, row):
        store_id = str(row.get("store_id") or "").strip()
        legacy = self._legacy_by_store.get(store_id) or {}
        legacy_summary = legacy.get("summary_json") if isinstance(legacy.get("summary_json"), dict) else {}
        db_summary = row.get("review_summary_json") if isinstance(row.get("review_summary_json"), dict) else {}
        db_taste = db_summary.get("taste_profile") if isinstance(db_summary.get("taste_profile"), dict) else {}
        legacy_taste = legacy_summary.get("taste_profile") if isinstance(legacy_summary.get("taste_profile"), dict) else {}

        summary_json = {
            "one_line_copy": str(
                db_summary.get("one_line_copy")
                or row.get("summary_3lines")
                or legacy_summary.get("one_line_copy")
                or ""
            ).strip(),
            "tags": db_summary.get("tags") if isinstance(db_summary.get("tags"), list) else legacy_summary.get("tags") if isinstance(legacy_summary.get("tags"), list) else [],
            "taste_profile": {
                "category_name": str(
                    db_taste.get("category_name")
                    or row.get("vibe")
                    or legacy_taste.get("category_name")
                    or ""
                ).strip(),
                "metrics": db_taste.get("metrics") if isinstance(db_taste.get("metrics"), list) else legacy_taste.get("metrics") if isinstance(legacy_taste.get("metrics"), list) else [],
            },
            "pro_tips": db_summary.get("pro_tips") if isinstance(db_summary.get("pro_tips"), list) else row.get("tips_json") if isinstance(row.get("tips_json"), list) else legacy_summary.get("pro_tips") if isinstance(legacy_summary.get("pro_tips"), list) else [],
            "negative_points": db_summary.get("negative_points") if isinstance(db_summary.get("negative_points"), list) else legacy_summary.get("negative_points") if isinstance(legacy_summary.get("negative_points"), list) else [],
        }

        signature_menu = row.get("signature_menu_json") if isinstance(row.get("signature_menu_json"), list) else legacy.get("must_eat_menus") if isinstance(legacy.get("must_eat_menus"), list) else []
        categories = row.get("categories_json") if isinstance(row.get("categories_json"), list) else []

        name = str(row.get("name") or legacy.get("name") or store_id).strip()
        address = str(row.get("address") or legacy.get("address") or "").strip()
        search_tags: list[str] = []
        search_tags.extend([str(x).strip() for x in signature_menu if str(x).strip()])
        search_tags.extend([str(x).strip() for x in categories if str(x).strip()])
        if name:
            search_tags.append(name)
        if address:
            search_tags.append(address)
        if isinstance(legacy.get("search_tags"), list):
            search_tags.extend([str(x).strip() for x in legacy.get("search_tags") if str(x).strip()])
        seen = set()
        dedup_tags: list[str] = []
        for tag in search_tags:
            if tag in seen:
                continue
            seen.add(tag)
            dedup_tags.append(tag)

        db_reviews = row.get("raw_reviews_json") if isinstance(row.get("raw_reviews_json"), list) else []
        legacy_reviews = legacy.get("raw_reviews") if isinstance(legacy.get("raw_reviews"), list) else []

        return {
            "id": row.get("store_id"),
            "naver_place_id": str(row.get("naver_place_id") or legacy.get("naver_place_id") or row.get("store_id") or ""),
            "name": name,
            "address": address,
            "latitude": float(row.get("lat")) if row.get("lat") is not None else float(legacy.get("latitude") or 37.5665),
            "longitude": float(row.get("lng")) if row.get("lng") is not None else float(legacy.get("longitude") or 126.9780),
            "ai_score": float(row.get("score") or 0),
            "ad_review_ratio": float(row.get("ad_review_ratio") or 0),
            "category": row.get("category") or summary_json["taste_profile"]["category_name"] or "",
            "categories": categories,
            "analysis_run_id": row.get("run_id"),
            "updated_at": row.get("updated_at"),
            "transport_info": str(row.get("transport_info") or legacy.get("transport_info") or address),
            "summary_json": summary_json,
            "must_eat_menus": signature_menu,
            "search_tags": dedup_tags,
            "original_url": row.get("url") or legacy.get("original_url") or "",
            "created_at": row.get("collected_at"),
            "raw_reviews": db_reviews if db_reviews else legacy_reviews,
        }
