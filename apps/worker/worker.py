import os

from redis import Redis
from rq import Connection, Queue, Worker


def main() -> None:
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    queue_name = os.getenv("RQ_QUEUE", "hidden_spot")

    conn = Redis.from_url(redis_url)
    with Connection(conn):
        worker = Worker([Queue(queue_name)])
        worker.work(with_scheduler=True)


if __name__ == "__main__":
    main()
