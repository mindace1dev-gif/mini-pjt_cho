"""웹 API 요청 본문 형식."""

from pydantic import BaseModel


class QueryRequest(BaseModel):
    """요청 본문. question 은 필수(제출 규약), session_id 는 대화를 이어 갈 때만 쓰는 선택 필드."""
    question: str
    session_id: str | None = None


class FeedbackRequest(BaseModel):
    """만족도 응답."""
    rating: int
    comment: str = ""


class SlotRequest(BaseModel):
    """점검으로 닫거나 열 슬롯."""
    date: str
    hour: int
    facility_id: str
    reason: str = "시설 점검"
