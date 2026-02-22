# Stable Deployment Guide (Netlify + Render + R2)

This guide follows the stable setup:

- Frontend: Netlify Free
- API: Render Web Service (Free)
- Worker: Render Background Worker (Starter)
- Database: Render Postgres Basic-256MB
- Queue: Render Key Value Starter
- Object storage: Cloudflare R2 (S3-compatible)

## 1) Prepare Cloudflare R2

1. Create buckets:
   - `hidden-spot-bronze`
   - `hidden-spot-silver`
   - `hidden-spot-gold`
   - `hidden-spot-artifacts`
2. Create S3 API token and save:
   - Access Key ID
   - Secret Access Key
3. Copy Account ID, then build endpoint:
   - `<accountid>.r2.cloudflarestorage.com`

## 2) Create Render resources

1. Create Postgres: `Basic-256MB`
2. Create Key Value: `Starter`
3. Create Web Service (API):
   - Type: Docker
   - Dockerfile path: `apps/api/Dockerfile`
4. Create Background Worker:
   - Type: Docker
   - Dockerfile path: `apps/worker/Dockerfile`

## 3) Set Render environment variables

### API service (`apps/api`)

- `DATABASE_URL=<render-postgres-internal-url>`
- `REDIS_URL=<render-keyvalue-internal-url>`
- `RQ_QUEUE=hidden_spot`
- `RQ_JOB_TIMEOUT_SEC=900`
- `CORS_ALLOW_ORIGINS=https://<your-netlify-site>.netlify.app,http://localhost:3000`

### Worker service (`apps/worker`)

- `DATABASE_URL=<render-postgres-internal-url>`
- `REDIS_URL=<render-keyvalue-internal-url>`
- `RQ_QUEUE=hidden_spot`
- `GEMINI_API_KEY=<your-gemini-key>`
- `GEMINI_MODEL=gemini-2.0-flash`
- `GEMINI_EMBED_MODEL=models/gemini-embedding-001`
- `PROMPT_VERSION=v1`
- `CHUNK_SIZE=80`
- `PLAYWRIGHT_HEADLESS=true`
- `CRAWL_RETRY_COUNT=2`
- `CRAWL_DELAY_MS=1200`
- `CRAWL_TIMEOUT_SEC=180`
- `MINIO_ENDPOINT=<accountid>.r2.cloudflarestorage.com`
- `MINIO_SECURE=true`
- `MINIO_ACCESS_KEY=<r2-access-key-id>`
- `MINIO_SECRET_KEY=<r2-secret-access-key>`
- `MINIO_BUCKET_BRONZE=hidden-spot-bronze`
- `MINIO_BUCKET_SILVER=hidden-spot-silver`
- `MINIO_BUCKET_GOLD=hidden-spot-gold`
- `MINIO_BUCKET_ARTIFACTS=hidden-spot-artifacts`

## 4) Deploy backend and verify health

After API deploy:

```bash
curl https://<render-api-domain>/health
```

Expected:

```json
{"status":"ok"}
```

## 5) Deploy frontend on Netlify

Repository already has `netlify.toml` (`frontend` base).

Set Netlify env vars:

- `NEXT_PUBLIC_API_URL=https://<render-api-domain>`
- `NEXT_PUBLIC_NAVER_MAPS_CLIENT_ID=<naver-client-id>`

Naver Cloud Platform -> Web Service URL(Referer) allowlist:

- `https://<your-netlify-site>.netlify.app`
- custom domain (if used)

## 6) Smoke test checklist

1. Open frontend page, confirm map and list render.
2. Submit one Naver map URL.
3. Verify API job flow:
   - `POST /jobs` returns `202` and `run_id`
   - `GET /jobs/{run_id}` changes `queued -> started/completed`
4. Verify worker logs show crawl/parse/llm stages.
5. Verify R2 buckets receive bronze/silver/gold/artifacts objects.

## 7) Optional stabilization

- If API cold starts are annoying on Free plan, move API to Starter.
- Typical stable cost baseline is around the previously agreed monthly budget.
