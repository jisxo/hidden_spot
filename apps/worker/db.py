import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone

import psycopg2
import psycopg2.extras


class WorkerDatabase:
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

    def update_snapshot(
        self,
        run_id: str,
        status: str,
        progress: int,
        bronze_path: str | None = None,
        silver_path: str | None = None,
        gold_path: str | None = None,
        error_reason: str | None = None,
    ) -> None:
        sql = """
        UPDATE store_snapshots
        SET status=%s,
            progress=%s,
            bronze_path=COALESCE(%s, bronze_path),
            silver_path=COALESCE(%s, silver_path),
            gold_path=COALESCE(%s, gold_path),
            error_reason=%s,
            updated_at=NOW()
        WHERE run_id=%s;
        """
        with self.conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (status, progress, bronze_path, silver_path, gold_path, error_reason, run_id))

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
