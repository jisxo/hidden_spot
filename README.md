# Hidden Spot: Reprocessable Data Engineering Pipeline

네이버 지도 URL 기반 매장 분석 서비스를, 동기 요청형 앱에서 **재처리 가능한 데이터 엔지니어링 파이프라인**으로 업그레이드한 프로젝트입니다.

## Runtime Source Of Truth
- Active runtime services:
  - API: `apps/api`
  - Worker: `apps/worker`
  - Compose entry: `infra/docker-compose.yml`
- Legacy (do not run/deploy/test target): `backend/`

## What This Project Demonstrates
- MinIO 기반 데이터 레이크 분리: Bronze / Silver / Gold / Artifacts
- FastAPI + Redis/RQ 기반 비동기 Job 처리 (202 응답, 상태 조회, 재시도)
- LLM Chunked Map-Reduce 요약 파이프라인
- Serving DB(Postgres/Supabase 호환)와 Lake 분리 아키텍처
- `run_id` 중심 추적, 단계별 JSON 로그, 실패 사유 기록

## Architecture
- Ingestion API: `POST /jobs`, `GET /jobs/{job_id}`
- Worker stages: `crawl -> parse -> llm -> (optional) embedding -> serving upsert`
- Data Lake (MinIO)
  - Bronze: raw html/meta
  - Silver: normalized reviews (`jsonl`)
  - Gold: final analysis + lineage metadata
  - Artifacts: prompt/chunk/hash index
- Serving DB (Postgres)
  - `stores`, `store_snapshots`, `analysis`, `embeddings(optional)`, `reviews(optional)`

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

## Data Contracts
- Bronze
  - `bronze/naver_map/store_id={store_id}/collected_at={ISO}/run_id={run_id}/reviews.html.gz`
  - `bronze/naver_map/store_id={store_id}/collected_at={ISO}/run_id={run_id}/store_meta.json`
- Silver
  - `silver/reviews/store_id={store_id}/dt={YYYY-MM-DD}/run_id={run_id}/reviews.jsonl`
- Gold
  - `gold/analysis/store_id={store_id}/dt={YYYY-MM-DD}/run_id={run_id}/analysis.json`

## Quality & Observability
- DQ checks:
  - `review_count > 0`
  - `store_id` required
  - `collected_at` required
  - rating range validation (when present)
- Structured logs:
  - `run_id`, `stage`, `status`, `duration_ms`, `payload`
- Failure handling:
  - snapshot `status/progress/error_reason` 업데이트
  - queue retry 적용

## Verified End-to-End Run
- Example run_id: `574c85f0-6777-43d0-9638-cb4d5e768b5e`
- Status: `completed`
- Bronze/Silver/Gold objects created with same `run_id`
- Serving upsert confirmed in `analysis`

## Local Run
```bash
docker compose -f infra/docker-compose.yml up --build
curl -X POST http://localhost:8000/jobs -H "content-type: application/json" -d '{"url":"https://map.naver.com/p/entry/place/37830333"}'
curl http://localhost:8000/jobs/<run_id>
```

## Frontend
프론트 실행 가이드는 `frontend/README.md`를 참고하세요.

## Deployment
- Stable deployment guide (Netlify + Render + R2): `docs/deploy-netlify-render-r2.md`
