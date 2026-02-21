# Hidden Spot Data Engineering Architecture

## Runtime Source Of Truth
- Active runtime services:
  - API: `apps/api`
  - Worker: `apps/worker`
  - Compose entry: `infra/docker-compose.yml`
- Legacy (do not run/deploy/test target): `backend/`

## Overview
- Ingestion trigger: `POST /jobs` (FastAPI)
- Execution model: Redis + RQ worker (retry enabled)
- Data lake: MinIO Bronze/Silver/Gold + Artifacts
- Serving DB: Postgres/Supabase-compatible schema (`stores`, `store_snapshots`, `analysis`)

## Diagram Labels
- User / Frontend
- FastAPI Job API
- Redis Queue (RQ)
- Worker Orchestrator
- Crawl Stage (Playwright)
- Parse Stage (HTML -> JSONL + DQ)
- LLM Stage (Chunk Map-Reduce)
- Embedding Stage (Optional)
- MinIO Bronze
- MinIO Silver
- MinIO Gold
- MinIO Artifacts
- Serving DB (Postgres/Supabase)
- Smart Search API (Synonym + Vector Optional)
- Observability (run_id / stage logs / error_reason)

## Mermaid
```mermaid
flowchart LR
  U[User / Web] --> A[FastAPI Job API]
  A -->|POST /jobs| Q[Redis Queue RQ]
  A -->|GET /jobs/{id}| S[(store_snapshots status)]

  Q --> W[Worker]
  W --> C[Crawl: Playwright]
  C --> B[(MinIO Bronze)]

  B --> P[Parse + DQ]
  P --> SI[(MinIO Silver)]

  SI --> L[LLM Chunk Map-Reduce]
  L --> G[(MinIO Gold)]
  L --> AR[(MinIO Artifacts)]

  L --> D[(Postgres analysis upsert)]
  D --> SS[Smart Search API]

  W --> O[JSON Logs run_id/stage/duration]
```

## End-to-end flow
1. User submits Naver Map URL to API.
2. API creates `run_id`, derives `store_id`, inserts `store_snapshots(status=queued)`, enqueues worker task.
3. Worker crawl stage collects raw page + reviews and writes Bronze:
   - `bronze/naver_map/store_id={store_id}/collected_at={ISO}/run_id={run_id}/reviews.html.gz`
   - `bronze/naver_map/store_id={store_id}/collected_at={ISO}/run_id={run_id}/store_meta.json`
4. Worker parse stage transforms HTML to JSONL and writes Silver:
   - `silver/reviews/store_id={store_id}/dt={YYYY-MM-DD}/run_id={run_id}/reviews.jsonl`
5. Worker LLM stage performs chunked map-reduce summarization and writes Gold:
   - `gold/analysis/store_id={store_id}/dt={YYYY-MM-DD}/run_id={run_id}/analysis.json`
6. Worker upserts serving row in `analysis` table and optionally embeddings table.

## Data lake contracts
- Bronze keeps reprocessable raw artifacts.
- Silver keeps normalized row-level review records (`review_key` surrogate hash).
- Gold stores final analysis + metadata:
  - `run_id`, `collected_at`, `store_id`
  - `crawler_version`, `parser_version`
  - `llm_model`, `prompt_version`, `prompt_hash`
  - `input_snapshot_path`, `tokens`, `chunk_count`

## DQ and observability
- DQ checks:
  - `review_count > 0`
  - `store_id` required
  - `collected_at` required
  - `rating` range check when rating exists
- Structured JSON logs from worker include:
  - `run_id`, `stage`, `status`, `duration_ms`, `payload`
- `GET /jobs/{job_id}` exposes snapshot status/progress/error.

## Local run
1. Copy `.env.example` to `.env` and fill `GEMINI_API_KEY` (optional).
2. Start stack:
   - `docker compose -f infra/docker-compose.yml up --build`
3. Create job:
   - `curl -X POST http://localhost:8000/jobs -H 'content-type: application/json' -d '{"url":"https://map.naver.com/p/entry/place/37830333"}'`
4. Poll status:
   - `curl http://localhost:8000/jobs/<run_id>`
5. Check MinIO console: `http://localhost:9001`
6. Optional smart search:
   - `curl 'http://localhost:8000/search/smart?q=국물'`

## Notes
- Anti-bot bypass logic is intentionally excluded.
- Crawl retries and polite delay are enabled via env vars.
