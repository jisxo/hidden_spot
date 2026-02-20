import os

from redis import Redis
from rq import Queue, Worker


def main() -> None:
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    queue_name = os.getenv("RQ_QUEUE", "hidden_spot")

    conn = Redis.from_url(redis_url)
    queue = Queue(queue_name, connection=conn)
    worker = Worker([queue], connection=conn)
    worker.work(with_scheduler=True)


if __name__ == "__main__":
    main()
