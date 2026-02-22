import gzip
import io
import json
import os
from typing import Any

from minio import Minio
from minio.error import S3Error
import urllib3


class MinioDataLakeClient:
    def __init__(self) -> None:
        endpoint_raw = (os.getenv("MINIO_ENDPOINT", "localhost:9000") or "").strip()
        endpoint, scheme = self._normalize_endpoint(endpoint_raw)
        access_key = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
        secret_key = os.getenv("MINIO_SECRET_KEY", "minioadmin")
        secure = os.getenv("MINIO_SECURE", "false").lower() == "true"
        if scheme == "https":
            secure = True

        self.bronze_bucket = os.getenv("MINIO_BUCKET_BRONZE", "hidden-spot-bronze")
        self.silver_bucket = os.getenv("MINIO_BUCKET_SILVER", "hidden-spot-silver")
        self.gold_bucket = os.getenv("MINIO_BUCKET_GOLD", "hidden-spot-gold")
        self.artifacts_bucket = os.getenv("MINIO_BUCKET_ARTIFACTS", "hidden-spot-artifacts")

        http_client = urllib3.PoolManager(
            timeout=urllib3.Timeout(connect=5.0, read=20.0),
            retries=urllib3.Retry(total=1, backoff_factor=0.2),
        )
        self.client = Minio(
            endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure,
            http_client=http_client,
        )

    def _normalize_endpoint(self, endpoint_raw: str) -> tuple[str, str]:
        if not endpoint_raw:
            return "localhost:9000", ""
        if endpoint_raw.startswith("https://"):
            host = endpoint_raw[len("https://") :]
            return (host.split("/", 1)[0] or "localhost:9000"), "https"
        if endpoint_raw.startswith("http://"):
            host = endpoint_raw[len("http://") :]
            return (host.split("/", 1)[0] or "localhost:9000"), "http"
        return (endpoint_raw.split("/", 1)[0] or "localhost:9000"), ""

    def put_bytes(self, bucket: str, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        self.client.put_object(bucket, key, io.BytesIO(data), len(data), content_type=content_type)

    def put_json(self, bucket: str, key: str, payload: Any) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.put_bytes(bucket, key, data, content_type="application/json")

    def put_gzip_text(self, bucket: str, key: str, text: str) -> None:
        gz = gzip.compress(text.encode("utf-8"))
        self.put_bytes(bucket, key, gz, content_type="application/gzip")

    def get_bytes(self, bucket: str, key: str) -> bytes:
        obj = self.client.get_object(bucket, key)
        try:
            return obj.read()
        finally:
            obj.close()
            obj.release_conn()

    def get_json(self, bucket: str, key: str) -> Any:
        return json.loads(self.get_bytes(bucket, key).decode("utf-8"))

    def get_gzip_text(self, bucket: str, key: str) -> str:
        return gzip.decompress(self.get_bytes(bucket, key)).decode("utf-8")

    def object_exists(self, bucket: str, key: str) -> bool:
        try:
            self.client.stat_object(bucket, key)
            return True
        except S3Error as exc:
            if exc.code == "NoSuchKey":
                return False
            raise

    def list_keys(self, bucket: str, prefix: str) -> list[str]:
        return [obj.object_name for obj in self.client.list_objects(bucket, prefix=prefix, recursive=True)]
