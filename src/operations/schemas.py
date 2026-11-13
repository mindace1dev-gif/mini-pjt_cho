"""운영 도메인의 기준값과 입출력 형식."""

from typing import TypedDict

EXPANSION_THRESHOLD = 0.85  # 이 이용률 이상인 시간대는 슬롯 확대 검토 대상
FACILITY_COUNT = {"BC": 5, "PM": 10}


class FeedbackEntry(TypedDict):
    """만족도 응답 하나 (의견은 마스킹된 상태로 저장)."""
    rating: int
    comment: str
    created_at: str


class HourlyUtilization(TypedDict):
    """시간대별 평균 이용률."""
    hour: int
    utilization: float
