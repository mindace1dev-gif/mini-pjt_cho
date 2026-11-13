"""POST /query API 서버 (제출 규약 형식) + 이용자용 웹 화면과 화면용 조회 API."""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from src.assistant.pipeline import answer_question
from src.assistant.schemas import QueryResponse
from src.operations.dashboard import dashboard
from src.operations.feedback import add_feedback
from src.reservation.service import close_slot, list_closures, open_slot
from src.reservation.tools import search_slots
from src.rules.retriever import list_articles
from src.web.schemas import FeedbackRequest, QueryRequest, SlotRequest

app = FastAPI(title="야구학습센터 예약 Agent")
INDEX_HTML = Path(__file__).resolve().parent / "static" / "index.html"


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    """이용자용 웹 화면 (예약 · 시설 안내 · 이용 규정)."""
    return FileResponse(INDEX_HTML)


@app.post("/query", response_model=QueryResponse)
def query(req: QueryRequest) -> dict:
    """질문을 받아 answer·contexts·trace 로 답한다. 같은 session_id 면 이전 대화를 이어서 해석한다."""
    session_id = (req.session_id or "").strip()[:64] or None
    return answer_question(req.question, session_id)


@app.get("/api/slots", include_in_schema=False)
def slots(date: str, member_type: str = "일반인") -> dict:
    """[화면용] 날짜별 시간대 빈자리 수. search_slots(파이썬 규칙)로 계산하며 LLM 을 쓰지 않는다."""
    if member_type not in ("일반인", "정기 회원"):
        raise HTTPException(400, "member_type 은 '일반인' 또는 '정기 회원'")
    result = search_slots.invoke({"date": date, "member_type": member_type})
    if not result.get("ok"):
        raise HTTPException(400, result.get("reason", "조회 실패"))
    hours = [{"hour": s["hour"],
              "batting": sum(f.startswith("BC-") for f in s["available"]),
              "pitching": sum(f.startswith("PM-") for f in s["available"]),
              "closed": len(s.get("closed_for_maintenance", [])),
              "note": s.get("note", "")} for s in result["slots"]]
    return {"date": date, "member_type": member_type, "totals": {"batting": 5, "pitching": 10}, "hours": hours}


@app.post("/api/feedback", include_in_schema=False)
def feedback(req: FeedbackRequest) -> dict:
    """[화면용] 답변 만족도(별점 1~5, 한 줄 의견)를 저장한다. 의견 속 개인정보는 가려 저장한다."""
    try:
        return {"ok": True, "saved": add_feedback(req.rating, req.comment)}
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/api/admin/dashboard", include_in_schema=False)
def admin_dashboard(days: int = 14) -> dict:
    """[관리자] 운영 지표. 파이썬 집계, 개인정보 없음."""
    return dashboard(max(1, min(days, 14)))


@app.get("/api/admin/closures", include_in_schema=False)
def admin_closures() -> list[dict]:
    """[관리자] 점검으로 닫힌 슬롯 목록."""
    return list_closures()


@app.post("/api/admin/closures", include_in_schema=False)
def admin_close(req: SlotRequest) -> dict:
    """[관리자] 슬롯을 점검으로 닫는다."""
    result = close_slot(req.date, req.hour, req.facility_id, req.reason)
    if not result["ok"]:
        raise HTTPException(400, result["reason"])
    return result


@app.delete("/api/admin/closures", include_in_schema=False)
def admin_open(req: SlotRequest) -> dict:
    """[관리자] 닫힌 슬롯을 다시 연다."""
    result = open_slot(req.date, req.hour, req.facility_id)
    if not result["ok"]:
        raise HTTPException(400, result["reason"])
    return result


@app.get("/api/rules", include_in_schema=False)
def rules() -> list[dict]:
    """[화면용] 센터 이용 규정 조항 목록. data/center_rules.md 를 그대로 읽는다."""
    return list_articles()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
