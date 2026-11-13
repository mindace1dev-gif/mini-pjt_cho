"""예약 상담 에이전트 도메인: 이용자 질문을 받아 도구를 골라 쓰고 근거와 함께 답한다.

- pipeline.py   : LCEL 체인 (입력 가드레일 → 규칙 판정 → Agent → 응답 구성), answer_question
- graph.py      : ReAct Agent 그래프 (도구 · 폴백/재시도/마스킹 미들웨어 · 세션 체크포인터)
- guardrails.py : 인젝션·개인정보 요청 감지, 시설 번호·타인 예약 여부 사전 판정
- prompts.py    : 시스템 프롬프트와 코드가 덧붙이는 안내 문구
- schemas.py    : POST /query 응답 형식 (answer · contexts · trace)
"""
