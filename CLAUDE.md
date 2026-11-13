# 프로젝트 규칙 · 야구학습센터 예약 Agent

> 무엇을·왜 만드는지는 @SERVICE.md 가 기준이다. 판단이 필요하면 SERVICE.md 를 먼저 본다.

## 작업 규칙
- SERVICE.md 에 없거나 애매한 것은 추측하지 말고 사용자에게 물어본다
- 한 번에 @TASKS.md 의 작업 하나만 한다. 끝나면 그 작업의 "확인 방법"대로 직접 실행해 보고 체크한다
- 계산·규칙 판정(회원 구분, 시간 정책, 시설 존재, 중복 예약)은 LLM 이 아니라 파이썬 코드로 한다. LLM 판정은 필요할 때 덧붙인다
- 사용자 허락 없이 새 프레임워크·라이브러리를 들이지 않는다. 에러 수정 중 처음 보는 패키지·함수는 사용자 확인 후 쓴다
- 모델 호출은 폴백 모델을 두어 한 모델이 실패해도 중단 없이 동작하게 한다
- 기획이 바뀌면 코드보다 SERVICE.md·TASKS.md 를 먼저 고친다

## 기술 스택
- Python, LangChain, LangGraph
- 모델은 Amazon Bedrock (ChatBedrockConverse) · us.anthropic.claude-sonnet-4-6 (계정 IAM 권한상 호출 가능한 모델. .env 의 BEDROCK_MODEL_ID 로 변경)
- 폴백 모델: Haiku 4.5 → global Sonnet 4.6 (ModelFallbackMiddleware, .env 의 BEDROCK_FALLBACK_MODEL_IDS 로 변경)
- Agent 생성은 langchain.agents 의 create_agent 를 쓴다
- 임베딩은 Amazon Bedrock Titan Embeddings
- API 서버는 FastAPI (src/web/server.py, 실행: python -m uvicorn src.web.server:app --port 8000)
- 트레이스는 LangSmith (환경변수는 .env 에서 읽는다)
- 평가는 RAGAS + LLM-as-Judge

## 적용 패턴 (빌드 체크리스트 · 8개)
| # | 패턴 | 이 프로젝트에서 |
|---|---|---|
| 1 | LCEL chain (Pydantic 구조화 출력) | 응답을 answer·contexts·trace 구조로 반환 (필수) |
| 2 | ReAct | create_agent 가 도구 3개 중 자율 선택 |
| 3 | RAG (하이브리드 검색) | 센터 이용 규정을 BM25 + 벡터 검색으로 조회 (필수) |
| 4 | 도구 다중 | 한 질의에서 check_membership → search_slots → create_reservation 결합 |
| 6 | 가드레일 | PII 요청·프롬프트 인젝션 차단, 정기 회원 전용 시간 정책 유지, 없는 시설 번호 파이썬 판정 |
| 8 | 미들웨어 | 이름·전화번호 마스킹 (answer·contexts·trace 모두), 재시도, 모델 폴백 |
| 11 | Observability | LangSmith 트레이스 기록 (필수) |
| 12 | 평가 | test_queries.csv 로 RAGAS·LLM-as-Judge 지표 산출 (필수) |

## 폴더 구조 (제출 규약 경로 + 도메인별 src/)
```
mini-pjt_{본인이름}/
├── src/
│   ├── agent.py · tools.py · retriever.py   # [제출 규약 진입점] 로직 없이 도메인 모듈을 다시 내보내기만 한다
│   ├── assistant/      # 예약 상담 에이전트
│   │   ├── pipeline.py     # LCEL 체인 (가드레일 → 규칙 판정 → Agent → 응답 구성), answer_question
│   │   ├── graph.py        # ReAct Agent (도구 · 폴백/재시도/마스킹 미들웨어 · 세션 체크포인터)
│   │   ├── guardrails.py   # 인젝션·개인정보 요청 감지, 시설 번호·타인 예약 여부 사전 판정
│   │   ├── prompts.py      # 시스템 프롬프트, 코드가 덧붙이는 안내 문구
│   │   └── schemas.py      # POST /query 응답 (answer · contexts · trace)
│   ├── reservation/    # 회원·슬롯·예약
│   │   ├── service.py      # 상태(예약·점검)와 규칙 판정, _STATE_LOCK
│   │   ├── tools.py        # check_membership · search_slots · create_reservation
│   │   ├── prompts.py      # 도구 설명(LLM 프롬프트), 안내 문구
│   │   └── schemas.py      # 회원 구분 상수, 결과 형식
│   ├── rules/          # 이용 규정 RAG
│   │   ├── retriever.py    # 조항 분할 · BM25 + Titan 벡터 · RRF
│   │   ├── tools.py        # retrieve_rules
│   │   ├── prompts.py · schemas.py
│   ├── operations/     # 관리자 운영
│   │   ├── dashboard.py    # 일일 방문자·이용률·확대 검토 시간대
│   │   ├── feedback.py     # 만족도 저장·집계
│   │   └── schemas.py      # 기준값(85%), 결과 형식
│   ├── evaluation/     # 품질 평가 (실행: python -m src.evaluation.runner --round 2)
│   │   ├── runner.py · metrics.py · report.py · prompts.py · schemas.py
│   ├── web/            # 화면·API
│   │   ├── server.py       # POST /query, GET /, 화면용·관리자 API
│   │   ├── schemas.py      # 요청 본문
│   │   └── static/index.html
│   └── shared/         # 공통
│       ├── config.py       # 경로, .env, 모델 ID, JSON 읽기
│       ├── llm.py          # Bedrock 채팅·폴백·임베딩 클라이언트
│       └── pii.py          # 이름·전화번호 마스킹, 마스킹 대상 이름
├── data/                      # 사용한 문서·데이터 (회원·슬롯·이용 이력 더미 JSON, 센터 이용 규정)
├── evaluation/                # 평가셋과 결과 (코드는 src/evaluation/)
│   ├── test_queries.csv       # 인-아웃 세트 (§4-4 스키마 필수 · 최종 채점 기준)
│   ├── round1_report.md · round1_results.json   # 1차 자체 평가 (Day 9)
│   └── round2_report.md · round2_results.json   # 2차 자체 평가 (Day 10 · 개선 후)
├── tests/
│   └── test_reservation_concurrency.py  # 동시 예약 원자성 테스트 (python -m unittest)
├── SERVICE.md                 # 서비스 스펙 (§4-3 템플릿 필수)
├── TASKS.md · CLAUDE.md
├── requirements.txt
└── README.md                  # §4-5 템플릿 준수
```

## src/ 배치 규칙
- 폴더는 기술 역할(utils·models)이 아니라 **업무 도메인**으로 나눈다: assistant(상담) · reservation(예약) · rules(규정) · operations(운영) · evaluation(평가) · web(화면·API)
- 도메인 폴더 안에는 그 도메인의 **실행 로직, 프롬프트(prompts.py), 입출력 형식(schemas.py)**을 함께 둔다. LLM 에 주는 문구(시스템 프롬프트·도구 설명·안내 문구)는 코드에 흩지 않고 prompts.py 에 둔다
- **shared/ 에는 두 도메인 이상이 함께 쓰는 것만** 둔다 (설정·LLM 클라이언트·마스킹). 한 도메인만 쓰면 그 도메인에 둔다
- 의존 방향: web·evaluation → assistant·operations → reservation·rules → shared. 아래 계층이 위 계층을 import 하지 않는다 (reservation·rules 는 assistant·operations·web·evaluation 을 모르고, shared 는 어떤 도메인도 모른다)
- 규칙 판정·상태 변경은 reservation/service.py 에만 둔다. tools.py 는 도구 형식으로 감싸기만 하고, web/server.py 는 도메인 함수만 호출한다
- import 는 `from src.<도메인>.<모듈> import ...` 절대 경로로 쓴다. 프로젝트 루트에서 실행한다 (`python -m ...`)
- `src/agent.py · tools.py · retriever.py` 는 제출 규약 경로라 지우지 않는다. 로직을 넣지 않고 도메인 모듈을 다시 내보내기만 한다
- 새 도메인이 생기면 `src/<도메인>/__init__.py` 의 docstring 에 역할과 파일 목록을 적고, 이 절과 폴더 구조를 함께 고친다

## 주고받는 형식 (제출 규약. 바꾸지 않는다)
```
POST /query
Content-Type: application/json
Body: {"question": "사용자 질의"}

Response:
{
  "answer": "근거 기반 응답",
  "contexts": [{"doc_id": "...", "text": "..."}, ...],
  "trace": [{"step": "retrieve", "input": "...", "output": "..."}, ...]
}
```
- 필수 요청 필드는 question 하나다. 선택 필드 session_id 를 주면 같은 세션의 이전 대화를 이어서 해석하고(LangGraph 체크포인터, 서버 메모리), 없으면 단일 턴으로 처리한다. 응답 키는 바꾸지 않는다
- contexts 에는 답의 근거(규정 조항, 도구 조회 결과)를 담는다
- trace 에는 retrieve 와 도구 호출 단계를 순서대로 남긴다
- 이름·전화번호 마스킹은 answer 뿐 아니라 contexts 와 trace 에도 적용한다

## 코드 규칙
- 파일 하나에 한 가지 역할만 둔다
- 함수와 도구에는 한국어 docstring 을 쓴다
- 비밀 값은 .env 에서 읽고 코드에 적지 않는다
- 도구로 조회한 결과만 근거로 답한다. 없는 회원·슬롯·규칙은 지어내지 않는다
- 예약·점검 상태를 바꾸는 코드는 reservation/service.py 의 _STATE_LOCK 안에서 "확인 → 확정"을 한 묶음으로 처리한다 (동시 요청 시 한 건만 성공)

## 하지 말 것
- 요청하지 않은 파일을 새로 만들지 않는다
- 기존 파일을 통째로 다시 쓰지 않는다. 바뀐 부분만 고친다
- evaluation/test_queries.csv 의 통과한 문항을 지우지 않는다
