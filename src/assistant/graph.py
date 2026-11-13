"""ReAct Agent 그래프: 도구 4개 + 폴백·재시도·출력 마스킹 미들웨어 + 세션 체크포인터."""

from datetime import date

from langchain.agents import create_agent
from langchain.agents.middleware import ModelFallbackMiddleware, ModelRetryMiddleware, after_model
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver

from src.assistant.prompts import SYSTEM_PROMPT
from src.reservation.tools import RESERVATION_TOOLS
from src.rules.tools import RULES_TOOLS
from src.shared.llm import chat_model, fallback_models
from src.shared.pii import KNOWN_NAMES, mask_text

AGENT_TOOLS = RESERVATION_TOOLS + RULES_TOOLS


@after_model
def mask_model_output(state, runtime):
    """[미들웨어] 모델이 낸 답변 문장의 이름·전화번호를 가린다."""
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and isinstance(last.content, str) and last.content:
        masked = mask_text(last.content, KNOWN_NAMES)
        if masked != last.content:
            return {"messages": [last.model_copy(update={"content": masked})]}
    return None


def build_agent():
    """ReAct Agent 를 만든다. 도구 4개 + 폴백·재시도·마스킹 미들웨어."""
    fallbacks = fallback_models()
    middleware = [ModelFallbackMiddleware(*fallbacks)] if fallbacks else []
    # 재시도는 폴백 안쪽에서 돌고, 끝내 실패하면 오류를 올려 폴백 모델로 넘어가게 한다
    middleware += [ModelRetryMiddleware(max_retries=1, on_failure="error"), mask_model_output]
    return create_agent(
        chat_model(),
        tools=AGENT_TOOLS,
        system_prompt=SYSTEM_PROMPT.format(today=date.today().isoformat()),
        middleware=middleware,
        checkpointer=InMemorySaver(),  # 세션(thread_id)별 대화 기록. 서버 메모리에만 둔다
        name="baseball_center_agent",
    )


AGENT = build_agent()
