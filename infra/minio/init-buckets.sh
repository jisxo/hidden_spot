#!/bin/sh
set -e

until mc alias set local http://minio:9000 "$MINIO_ACCESS_KEY" "$MINIO_SECRET_KEY"; do
  echo "waiting for minio..."
  sleep 2
done

mc mb -p "local/${MINIO_BUCKET_BRONZE}" || true
mc mb -p "local/${MINIO_BUCKET_SILVER}" || true
mc mb -p "local/${MINIO_BUCKET_GOLD}" || true
mc mb -p "local/${MINIO_BUCKET_ARTIFACTS}" || true

echo "buckets ready"
