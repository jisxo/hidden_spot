import os

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from redis import Redis
from rq import Queue
from rq.job import Job
from rq.retry import Retry

from apps.api.db import ApiDatabase
from apps.api.store_id import derive_store_id
from libs.common.run_context import new_run_id, utc_now, isoformat_z


class JobCreateRequest(BaseModel):
    url: str


class JobCreateResponse(BaseModel):
    job_id: str
    run_id: str
    store_id: str
    status: str


app = FastAPI(title="Hidden Spot Jobs API")
_db = ApiDatabase()


def _queue() -> Queue:
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    queue_name = os.getenv("RQ_QUEUE", "hidden_spot")
    conn = Redis.from_url(redis_url)
    return Queue(name=queue_name, connection=conn)


@app.on_event("startup")
def startup() -> None:
    _db.ensure_tables()


@app.post("/jobs", response_model=JobCreateResponse, status_code=202)
def create_job(payload: JobCreateRequest):
    url = payload.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="url is required")

    run_id = new_run_id()
    collected_at = isoformat_z(utc_now())
    store_id = derive_store_id(url)

    _db.upsert_store(store_id=store_id, url=url)
    _db.create_snapshot(
        store_id=store_id,
        collected_at_iso=collected_at,
        run_id=run_id,
        url=url,
        status="queued",
    )

    q = _queue()
    rq_job = q.enqueue(
        "apps.worker.tasks.process_job",
        kwargs={
            "run_id": run_id,
            "store_id": store_id,
            "url": url,
            "collected_at_iso": collected_at,
        },
        job_id=run_id,
        retry=Retry(max=3, interval=[10, 30, 60]),
        result_ttl=86400,
        failure_ttl=604800,
    )

    return JobCreateResponse(job_id=rq_job.id, run_id=run_id, store_id=store_id, status="queued")


@app.get("/jobs/{job_id}")
def get_job(job_id: str):
    snapshot = _db.get_snapshot(run_id=job_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail="job not found")

    queue_status = None
    try:
        job = Job.fetch(job_id, connection=_queue().connection)
        queue_status = job.get_status(refresh=True)
    except Exception:
        queue_status = None

    snapshot["queue_status"] = queue_status
    return snapshot


@app.get("/health")
def health_check():
    return {"status": "ok"}
