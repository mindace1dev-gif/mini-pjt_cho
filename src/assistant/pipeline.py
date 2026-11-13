"""예약 상담 LCEL 체인: 입력 가드레일 → 규칙 판정 → Agent → 응답 구성(answer · contexts · trace)."""

import ast
import json
from uuid import uuid4

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableLambda

from src.assistant.graph import AGENT
from src.assistant.guardrails import check_facilities, guard_input
from src.assistant.prompts import (GUEST_GUARANTEE, MEMBER_ONLY_GUARANTEE, PII_REFUSAL_GUARANTEE, REFUSAL_PHRASES,
                                   SLOT_STATUS_WORDS)
from src.assistant.schemas import Context, QueryResponse, TraceStep, context_doc_id
from src.reservation.service import mentions_member_only_hour
from src.shared.pii import KNOWN_NAMES, mask_text


def _parse(content) -> object:
    """ToolMessage 내용을 파이썬 객체로 바꾼다."""
    if not isinstance(content, str):
        return content
    for loader in (json.loads, ast.literal_eval):
        try:
            return loader(content)
        except (ValueError, SyntaxError):
            continue
    return content


def _dump(obj) -> str:
    """객체를 가려진 JSON 문자열로 만든다."""
    text = obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False)
    return mask_text(text, KNOWN_NAMES)


def run_agent(state: dict) -> dict:
    """ReAct Agent 를 실행한다. session_id 가 같으면 이전 대화를 이어 가고, 없으면 새 대화로 처리한다."""
    thread_id = state.get("session_id") or f"single-{uuid4()}"
    result = AGENT.invoke({"messages": [HumanMessage(state["message"])]},
                          config={"run_name": "baseball_center_agent", "tags": ["mini-pjt"],
                                  "configurable": {"thread_id": thread_id}})
    messages = result["messages"]
    # 응답·근거·처리 과정은 이번 질문 이후의 메시지만으로 만든다 (이전 턴의 도구 결과가 섞이지 않게)
    last_human = max(i for i, m in enumerate(messages) if isinstance(m, HumanMessage))
    return {**state, "messages": messages[last_human:]}


def build_response(state: dict) -> dict:
    """메시지 기록에서 answer·contexts·trace 를 뽑아 규약 형식으로 만든다. 모든 필드를 마스킹한다."""
    calls = {}
    contexts: list[Context] = [Context(doc_id=c["doc_id"], text=_dump(c["text"])) for c in state.get("pre_contexts", [])]
    trace = [TraceStep(**{k: _dump(v) for k, v in s.items()}) for s in state["trace"]]
    answer = ""
    not_member = False  # check_membership 이 정기 회원으로 인정하지 않았는가
    member_only_blocked = False  # 예약 도구가 '정기 회원 전용'을 이유로 예약을 막았는가
    verified_member = False  # 확인된 정기 회원이 있는가
    for msg in state["messages"]:
        if isinstance(msg, AIMessage):
            for call in msg.tool_calls:
                calls[call["id"]] = call
            if msg.content and not msg.tool_calls:
                answer = msg.text if hasattr(msg, "text") else str(msg.content)
        elif isinstance(msg, ToolMessage):
            call = calls.get(msg.tool_call_id, {"name": msg.name, "args": {}})
            output = _parse(msg.content)
            if call["name"] == "check_membership" and isinstance(output, dict):
                if output.get("verified"):
                    verified_member = True
                else:
                    not_member = True
            if call["name"] == "create_reservation" and "정기 회원 전용" in json.dumps(output, ensure_ascii=False):
                member_only_blocked = True
            step = "retrieve" if call["name"] == "retrieve_rules" else f"tool:{call['name']}"
            trace.append(TraceStep(step=step, input=_dump(call["args"]), output=_dump(output)))
            if call["name"] == "retrieve_rules" and isinstance(output, list):
                contexts += [Context(doc_id=d["doc_id"], text=_dump(d["text"])) for d in output]
            else:
                contexts.append(Context(doc_id=context_doc_id(call["name"], call["args"]), text=_dump(output)))
    missing = [u["message"] for u in state.get("unknown_facilities", [])
               if not (u["facility"] in answer and "없" in answer)]
    if missing:  # 모델이 안내를 빠뜨려도 규칙 판정 결과는 반드시 답에 담는다
        answer = " ".join(missing) + "\n\n" + answer
    # 전용 시간 거절 사유는 반드시 안내한다: 예약 도구가 막았거나, 확인된 정기 회원 없이 17시 슬롯을 요청했을 때
    asked_member_hour = mentions_member_only_hour(state["question"]) and not verified_member
    if (member_only_blocked or asked_member_hour) and "정기 회원 전용" not in answer:
        answer = MEMBER_ONLY_GUARANTEE + answer
    # 다른 사람의 개인정보를 물으면 거절 사실을 반드시 밝힌다 (가드레일이 감지한 경우)
    if state.get("pii_request") and not any(p in answer for p in REFUSAL_PHRASES):
        answer = PII_REFUSAL_GUARANTEE + answer
    # 다른 사람의 예약을 물었으면 예약 여부는 반드시 답한다 (파이썬 조회 결과)
    if state.get("slot_status") and not any(k in answer for k in SLOT_STATUS_WORDS):
        answer += "\n\n" + state["slot_status"]
    if not_member and "일반인" not in answer:  # 회원 불인정이어도 일반인 이용 가능함은 반드시 안내한다
        answer += GUEST_GUARANTEE
    answer = mask_text(answer, KNOWN_NAMES)
    trace.append(TraceStep(step="answer", input=_dump(state["question"]), output=answer))
    return QueryResponse(answer=answer, contexts=contexts, trace=trace).model_dump()


# LCEL 체인: 입력 가드레일 → 시설 규칙 판정 → Agent → 구조화 응답
chain = (RunnableLambda(guard_input) | RunnableLambda(check_facilities)
         | RunnableLambda(run_agent) | RunnableLambda(build_response))


def answer_question(question: str, session_id: str | None = None) -> dict:
    """질문 하나를 처리해 {answer, contexts, trace} 를 돌려준다. session_id 를 주면 같은 세션의 대화를 이어 간다."""
    return chain.invoke({"question": question, "session_id": session_id})
