"""이용자 만족도: 답변별 별점·의견 저장과 집계."""

from collections import Counter
from datetime import datetime

from src.operations.schemas import FeedbackEntry
from src.shared.pii import KNOWN_NAMES, mask_text

_FEEDBACK: list[FeedbackEntry] = []  # 만족도 응답. 서버 메모리에만 둔다


def add_feedback(rating: int, comment: str = "") -> FeedbackEntry:
    """만족도 응답을 저장한다. 별점은 1~5 만 받고, 의견 속 이름·전화번호는 가려서 저장한다."""
    if not isinstance(rating, int) or not 1 <= rating <= 5:
        raise ValueError("별점은 1~5 사이 정수여야 함")
    entry = {"rating": rating, "comment": mask_text((comment or "").strip()[:200], KNOWN_NAMES),
             "created_at": datetime.now().strftime("%Y-%m-%d %H:%M")}
    _FEEDBACK.append(entry)
    return entry


def feedback_summary() -> dict:
    """만족도 평균·분포·최근 의견."""
    ratings = [f["rating"] for f in _FEEDBACK]
    dist = Counter(ratings)
    return {"count": len(ratings),
            "average": round(sum(ratings) / len(ratings), 2) if ratings else None,
            "distribution": [{"rating": r, "count": dist.get(r, 0)} for r in range(5, 0, -1)],
            "recent": [f for f in reversed(_FEEDBACK) if f["comment"]][:5]}
