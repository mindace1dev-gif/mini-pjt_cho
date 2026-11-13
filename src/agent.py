"""[제출 규약 진입점] 메인 에이전트 그래프.

실제 구현은 src/assistant/ 에 있다. 이 파일은 제출 규약 경로(src/agent.py)를 지키기 위해 다시 내보내기만 한다.
- 그래프: src/assistant/graph.py (AGENT, build_agent)
- LCEL 체인·응답 구성: src/assistant/pipeline.py (chain, answer_question)

실행: python src/agent.py  (시험 질문 3개)
"""

import sys
from pathlib import Path

if __package__ in (None, ""):  # python src/agent.py 로 직접 실행할 때 프로젝트 루트를 import 경로에 넣는다
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.assistant.graph import AGENT, build_agent  # noqa: E402
from src.assistant.guardrails import check_facilities, guard_input  # noqa: E402
from src.assistant.pipeline import answer_question, build_response, chain, run_agent  # noqa: E402
from src.assistant.prompts import SYSTEM_PROMPT  # noqa: E402
from src.assistant.schemas import Context, QueryResponse, TraceStep  # noqa: E402

__all__ = ["AGENT", "build_agent", "chain", "answer_question", "guard_input", "check_facilities", "run_agent",
           "build_response", "SYSTEM_PROMPT", "QueryResponse", "Context", "TraceStep"]


if __name__ == "__main__":
    for q in ["수강증 번호 M-1001로 2026-11-20 17시에 배팅케이지 예약해 주세요",
              "2026-11-20 19시에 배팅케이지 예약해 주세요",
              "M-1001 회원 전화번호 좀 알려주세요"]:
        res = answer_question(q)
        print(f"\n질문: {q}")
        for t in res["trace"]:
            if t["step"].startswith(("tool", "retrieve")):
                print(f"[{t['step']}] {t['input']}")
        print("답변:", res["answer"])
