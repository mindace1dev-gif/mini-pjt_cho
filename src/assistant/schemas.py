"""예약 상담 에이전트의 입출력 형식. POST /query 응답(answer · contexts · trace)은 제출 규약이다."""

from pydantic import BaseModel, Field


class Context(BaseModel):
    """답변 근거 하나."""
    doc_id: str
    text: str


class TraceStep(BaseModel):
    """처리 단계 하나."""
    step: str
    input: str
    output: str


class QueryResponse(BaseModel):
    """POST /query 응답 형식 (제출 규약)."""
    answer: str = Field(description="근거 기반 응답")
    contexts: list[Context] = Field(default_factory=list)
    trace: list[TraceStep] = Field(default_factory=list)


def context_doc_id(tool_name: str, args: dict) -> str:
    """도구 조회 결과의 근거 ID 를 만든다. 예: members.json#M-1001, slots.json#2026-11-20 19시 BC-3"""
    if tool_name == "check_membership":
        key = args.get("card_no") or args.get("qr") or "이름+전화번호"
        return f"members.json#{key}"
    if tool_name in ("search_slots", "create_reservation"):
        hour = args.get("hour")
        when = f"{args.get('date')}{'' if hour is None else f' {hour}시'}"
        return f"slots.json#{when}{' ' + args['facility_id'] if args.get('facility_id') else ''}"
    return tool_name
