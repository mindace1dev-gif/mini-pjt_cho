"""입력 가드레일과 파이썬 사전 판정 단계 (LCEL 체인의 앞부분)."""

import re

from src.assistant.prompts import (FACILITY_FACT, INJECTION_FLAG, PII_REQUEST_FLAG, SECURITY_NOTICE, SLOT_FACT,
                                   SLOT_FREE, SLOT_RESERVED, SLOT_STATUS)
from src.assistant.schemas import context_doc_id
from src.reservation.service import find_unknown_facilities, parse_slot_mention
from src.reservation.tools import search_slots

INJECTION_PATTERNS = re.compile(
    r"(이전|위의?|모든)\s*(지시|명령|규칙).{0,10}(무시|잊)|무시하고|시스템\s*프롬프트|ignore\s+(all|previous)|규칙을\s*(바꿔|무시)",
    re.IGNORECASE,
)
PII_REQUEST_PATTERNS = re.compile(r"(전화번호|연락처|휴대폰|핸드폰|이름).{0,15}(알려|뭐|조회|보여)")
PHONE_IN_TEXT = re.compile(r"01[016789]-?\d{3,4}-?\d{4}")


def guard_input(request: dict) -> dict:
    """[가드레일] 프롬프트 인젝션·타인 개인정보 요청을 감지해 경고를 붙인다."""
    question, session_id = request["question"], request.get("session_id")
    flags = []
    if INJECTION_PATTERNS.search(question):
        flags.append(INJECTION_FLAG)
    pii_request = bool(PII_REQUEST_PATTERNS.search(question) and not PHONE_IN_TEXT.search(question))
    if pii_request:
        flags.append(PII_REQUEST_FLAG)
    message = question
    if flags:
        message += SECURITY_NOTICE.format(flags=" / ".join(flags))
    step = {"step": "guardrail_input", "input": question, "output": "; ".join(flags) or "통과"}
    return {"question": question, "session_id": session_id, "message": message, "trace": [step],
            "pii_request": pii_request}


def check_facilities(state: dict) -> dict:
    """[규칙 판정] 질문 속 시설 번호가 실제로 있는지 파이썬으로 확인해 사실을 Agent 에 전달한다."""
    unknown = find_unknown_facilities(state["question"])
    message = state["message"]
    if unknown:
        message += FACILITY_FACT.format(facts=" ".join(u["message"] for u in unknown))
    step = {"step": "facility_check", "input": state["question"],
            "output": "; ".join(u["message"] for u in unknown) or "통과"}
    trace = state["trace"] + [step]

    # 다른 사람의 예약을 물으면 예약 여부만 답해야 하므로, 질문 속 슬롯을 파이썬이 직접 조회한다
    slot_status, pre_contexts = None, []
    slot = parse_slot_mention(state["question"]) if state.get("pii_request") else None
    if slot:
        args = {"date": slot["date"], "hour": slot["hour"], "facility_id": slot["facility_id"], "member_type": "정기 회원"}
        result = search_slots.invoke(args)
        reserved = result.get("ok") and slot["facility_id"] not in result["slots"][0]["available"]
        slot_status = SLOT_STATUS.format(date=slot["date"], hour=slot["hour"], facility_name=slot["facility_name"],
                                         status=SLOT_RESERVED if reserved else SLOT_FREE)
        message += SLOT_FACT.format(slot_status=slot_status)
        trace.append({"step": "tool:search_slots", "input": args, "output": result})
        pre_contexts.append({"doc_id": context_doc_id("search_slots", args), "text": result})
    return {**state, "message": message, "unknown_facilities": unknown, "trace": trace,
            "slot_status": slot_status, "pre_contexts": pre_contexts}
