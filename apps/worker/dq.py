from typing import Any

_PORTAL_NOISE_MARKERS = (
    "본문 바로가기",
    "주 메뉴 바로가기",
    "내정보 보기",
    "프로필 사진 변경",
    "네이버ID 보안설정",
    "N Pay",
    "환경설정",
)


class DQError(Exception):
    pass


class InsufficientReviewsError(DQError):
    def __init__(self, review_count: int, min_required: int) -> None:
        self.review_count = review_count
        self.min_required = min_required
        super().__init__(
            f"리뷰 수가 부족해 AI 미식 가이드를 만들 수 없습니다. 현재 {review_count}개가 수집되었고 최소 {min_required}개가 필요합니다."
        )


def _is_portal_noise_text(text: str) -> bool:
    if not text:
        return False
    hits = sum(1 for marker in _PORTAL_NOISE_MARKERS if marker in text)
    return hits >= 2


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

    noise_count = 0
    for review in reviews:
        if _is_portal_noise_text(str(review.get("text") or "")):
            noise_count += 1

        rating = review.get("rating")
        if rating is None:
            continue
        if rating < 0 or rating > 5:
            raise DQError("DQ failed: rating out of range [0, 5]")

    if noise_count >= max(3, int(len(reviews) * 0.5)):
        raise DQError("DQ failed: reviews look like portal boilerplate, not place reviews")
