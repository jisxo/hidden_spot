import os
from contextlib import contextmanager

import psycopg2
import psycopg2.extras


class ApiDatabase:
    def __init__(self) -> None:
        self.database_url = os.getenv("DATABASE_URL", "postgresql://hidden_spot:hidden_spot@localhost:5432/hidden_spot")

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
            name TEXT,
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
        """
        with self.conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)

    def upsert_store(self, store_id: str, url: str) -> None:
        sql = """
        INSERT INTO stores (store_id, url) VALUES (%s, %s)
        ON CONFLICT (store_id)
        DO UPDATE SET url = EXCLUDED.url, updated_at = NOW();
        """
        with self.conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (store_id, url))

    def create_snapshot(self, store_id: str, collected_at_iso: str, run_id: str, url: str, status: str) -> None:
        sql = """
        INSERT INTO store_snapshots (store_id, collected_at, run_id, url, status, progress)
        VALUES (%s, %s, %s, %s, %s, %s);
        """
        with self.conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (store_id, collected_at_iso, run_id, url, status, 0))

    def get_snapshot(self, run_id: str):
        with self.conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM store_snapshots WHERE run_id = %s", (run_id,))
                return cur.fetchone()
