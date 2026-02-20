from typing import Any


class DQError(Exception):
    pass


def validate_reviews(
    reviews: list[dict[str, Any]],
    store_id: str,
    collected_at: str,
) -> None:
    if not reviews:
        raise DQError("DQ failed: review_count must be > 0")

    if not store_id:
        raise DQError("DQ failed: store_id is required")

    if not collected_at:
        raise DQError("DQ failed: collected_at is required")

    for review in reviews:
        rating = review.get("rating")
        if rating is None:
            continue
        if rating < 0 or rating > 5:
            raise DQError("DQ failed: rating out of range [0, 5]")
