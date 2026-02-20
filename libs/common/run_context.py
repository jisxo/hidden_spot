import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def isoformat_z(ts: datetime) -> str:
    return ts.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def date_partition(ts: datetime) -> str:
    return ts.astimezone(timezone.utc).strftime("%Y-%m-%d")


def new_run_id() -> str:
    return str(uuid.uuid4())


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


@dataclass
class RunContext:
    run_id: str
    collected_at: datetime
    store_id: str

    @property
    def collected_at_iso(self) -> str:
        return isoformat_z(self.collected_at)

    @property
    def dt(self) -> str:
        return date_partition(self.collected_at)
