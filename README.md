# 미니 PJT: 야구학습센터 예약 Agent

## 무엇을 푸나
야구학습센터 이용자들은 빈자리를 모른 채 방문하다 보니, 18~20시 피크에 1시간 가까이 기다리거나 헛걸음하는 경우가 많습니다. 그래서 이용자가 자연어로 물어보면 빈 시간을 찾아 바로 예약해 주는 예약 에이전트를 만들었습니다. 에이전트는 수강증으로 정기 회원 여부를 확인하고, 실제 예약 현황을 조회해 가능한 시간만 안내하며, 예약이 불가하면 센터 이용 규정을 근거로 이유와 대안 시간을 제시합니다. 17시 정기 회원 전용 같은 규칙은 코드로 판정해 지시 우회 시도에도 깨지지 않게 했고, 이름과 전화번호는 항상 가려서 보여 줍니다. 결과적으로 이용자는 헛걸음 없이 시설을 이용하고, 센터는 예약 기록으로 혼잡 시간대를 파악해 운영을 개선하는 것이 목표입니다. (상세: [SERVICE.md](SERVICE.md))

## 활용한 패턴 (Day 1~7)
- Day 1: LCEL chain (Pydantic 구조화 출력) — `입력 가드레일 | 시설 규칙 판정 | Agent | 응답 구성` 을 LCEL 로 잇고, 응답을 Pydantic `QueryResponse`(answer·contexts·trace) 로 반환
- Day 2: RAG (하이브리드 검색) — 센터 이용 규정을 조항 단위로 쪼개 BM25(어절 + 글자 2-gram) 와 Titan 벡터 검색 결과를 RRF 로 합침
- Day 3: ReAct — `create_agent` 가 도구 4개(check_membership, search_slots, create_reservation, retrieve_rules) 중 스스로 골라 호출
- Day 4: 도구 다중 — 한 질의에서 회원 확인 → 빈 슬롯 조회 → 예약을 이어서 결합
- Day 5: 가드레일 — 입력 단계에서 프롬프트 인젝션·타인 개인정보 요청을 감지해 경고를 붙이고, 예약 도구가 수강증을 직접 재검증해 프롬프트가 뚫려도 17시 슬롯(17:00~18:00) 정기 회원 전용 정책을 지킴. 없는 시설 번호는 파이썬이 판정해 예약을 막고 안내를 보장
- Day 5: 미들웨어 — 모델 출력의 이름·전화번호를 가리는 `after_model` 미들웨어, 재시도 `ModelRetryMiddleware`, 모델 폴백 `ModelFallbackMiddleware`(Sonnet 4.6 → Haiku 4.5 → global Sonnet 4.6). 최종 응답의 answer·contexts·trace 도 한 번 더 마스킹
- Day 7: 단기 메모리 — LangGraph 체크포인터(`InMemorySaver`)로 세션별 대화를 이어 감. "6번 예약" → "3번" 처럼 앞 대화를 이어서 해석
- Day 7: Observability — LangSmith 로 Agent 실행 트레이스 기록 (`.env` 의 LANGSMITH_* 설정)
- Day 7: 평가 — test_queries.csv 20건을 규칙 채점 + LLM-as-Judge 로 판정하고 RAGAS 4개 지표 산출

## 아키텍처
```
웹 화면 (GET /) 예약·시설 안내·이용 규정·관리자   src/web/static/index.html
   │
POST /query {"question", "session_id"(선택)}  src/web/server.py (FastAPI)
   │
   ▼  LCEL chain                              src/assistant/pipeline.py
[guard_input]   인젝션·타인 PII 요청 감지 → 경고 부착, trace 기록
   │
[check_facilities] 질문 속 시설 번호를 파이썬으로 판정 (없는 번호면 사실 전달)
                 타인 예약 질문이면 질문 속 슬롯을 파이썬이 search_slots 로 직접 조회해 예약 여부 전달
   │
[run_agent]     create_agent (ChatBedrockConverse · Claude Sonnet 4.6, 실패 시 폴백 모델)
   │   체크포인터: session_id 별 대화 기록 (없으면 단일 턴)
   │   ├─ check_membership    ← data/members.json   (수강증 번호 / 이름+전화 / QR, 만기 확인)
   │   ├─ search_slots        ← data/slots.json     (17시 정기 회원 전용, 만석 표시)
   │   ├─ create_reservation  ← data/slots.json     (수강증 재검증, 중복·점검·없는 시설 차단, 잠금으로 확인·확정 한 묶음)
   │   └─ retrieve_rules      ← src/rules/retriever.py (규정 BM25 + Titan 벡터, RRF)
   │   미들웨어: 모델 폴백 · 재시도 · 출력 마스킹(after_model)
   │
[build_response] 이번 질문 이후 메시지 → answer · contexts · trace
                 시설·17시 전용·일반인·개인정보 거절·타인 예약 여부 안내 누락 시 코드가 보완, 전체 PII 마스킹
   │
   ▼
{"answer", "contexts": [{"doc_id","text"}], "trace": [{"step","input","output"}]}

LangSmith: 전 과정 트레이스 기록

화면용 조회 API (LLM 미사용, 파이썬 계산)
  GET /api/slots · /api/rules          시설 안내 빈자리, 이용 규정 원문
  GET /api/admin/dashboard             일일 방문자·시간대·시설별 이용률, 확대 검토 시간대 (src/operations/)
  GET·POST·DELETE /api/admin/closures  점검 슬롯 닫기·열기
  POST /api/feedback                   답변 만족도 (의견 속 개인정보 마스킹)
```
- 예약은 메모리에서만 갱신하고 원본 JSON 은 바꾸지 않는다. 평가를 반복해도 같은 상태에서 시작한다.
- 필수 요청 필드는 question 하나다(제출 규약). 선택 필드 session_id 를 주면 같은 세션의 앞 대화를 이어서 해석하고, 없으면 단일 턴으로 처리한다. 응답 키는 그대로다.

## 실행 방법
```bash
pip install -r requirements.txt

# .env 에 아래 값 설정
# AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION
# LANGSMITH_TRACING, LANGSMITH_API_KEY, LANGSMITH_PROJECT
# (선택) BEDROCK_MODEL_ID  기본값 us.anthropic.claude-sonnet-4-6
# (선택) BEDROCK_FALLBACK_MODEL_IDS  쉼표 구분, 기본값 Haiku 4.5, global Sonnet 4.6

# API 서버 + 웹 채팅 화면
python -m uvicorn src.web.server:app --port 8000
# 브라우저에서 http://127.0.0.1:8000 → 예약(채팅) · 시설 안내(시간대별 빈자리) · 이용 규정 · 관리자(대시보드·슬롯 관리·만족도)
# http://127.0.0.1:8000/docs → API 테스트
curl -X POST http://localhost:8000/query -H "Content-Type: application/json" \
     -d '{"question": "수강증 번호 M-1001로 2026-11-20 17시에 배팅케이지 예약해 주세요"}'

# 콘솔에서 바로 시험
python src/agent.py

# 자체 평가 (결과: evaluation/round{N}_report.md)
python -m src.evaluation.runner --round 1

# 동시 예약 원자성 테스트 (LLM 호출 없음)
python -m unittest tests.test_reservation_concurrency -v
```

## RAGAS 평가 결과
2차(최종 코드, 재평가 2) 기준. RAGAS 정의를 따라 LLM-as-Judge 로 계산했다. (ragas 라이브러리가 Python 3.14 에서 설치되지 않아 같은 정의로 직접 구현, reference 는 expected_traits)
- context_recall: 0.93
- context_precision: 0.98
- faithfulness: 0.85
- answer_relevancy: 0.55

answer_relevancy 가 낮은 것은 답변에 예약 표·안내 문구가 붙어, 답변에서 거꾸로 만든 질문이 원래 질문과 표현이 달라지기 때문으로 본다.

## 인-아웃 세트 통과율 (자체 평가)
- 1차: 14 / 20 통과 (70%) — [evaluation/round1_report.md](evaluation/round1_report.md)
- 2차 (개선 후): 20 / 20 통과 (100%) — [evaluation/round2_report.md](evaluation/round2_report.md) (최종 코드 반복 실행 2회 모두 20/20, 판정 오류 0건)
- 개선폭: +6 건 (주요 개선 사항: 단일 턴에서 되묻지 않고 직접 조회해 대안까지 제시, 타인 예약은 여부만 조회해 답함, 요청이 불가할 때 임의 예약하지 않음, 없는 시설 번호를 파이썬으로 판정, 필수 안내(17시 전용·일반인 이용·개인정보 거절·타인 예약 여부)를 코드로 보장, 모호한 판정 기준 문구 정리)

## 트라이앤에러 회고
- 시도했지만 실패한 접근 · 왜 실패했는가
  - ragas 라이브러리 설치: Python 3.14 에서 의존 패키지(scikit-network) 빌드가 실패하고, --no-deps 설치는 최신 langchain_community 에서 사라진 모듈을 불러와 쓸 수 없었다. → RAGAS 정의대로 LLM-as-Judge 로 직접 구현
  - 내장 PIIMiddleware: 한국 전화번호·이름을 지원하지 않고, 입력까지 가리면 "이름+전화번호로 회원 확인" 기능이 깨졌다. → 출력에만 적용하는 커스텀 after_model 미들웨어
  - "되묻지 말고 직접 처리하라" 규칙(루프 1회차): 통과율은 올랐지만 없는 6번 대신 1번을 임의 예약하는 부작용이 생겼다. → 3회차에 "불가하면 대신 예약하지 않는다" 규칙으로 바로잡음
  - 없는 시설 번호 안내를 프롬프트로 3번 고치려 했으나(지시 추가, 도구 인자 추가, 답변 규칙) 모두 반영률 0~1/3 이었다. 모델이 시스템 프롬프트로 시설 목록을 이미 알아 도구로 확인할 필요를 느끼지 않았기 때문 → 규칙 판정을 LLM 에 맡긴 것이 원인이라고 보고 파이썬 판정으로 전환
  - 판정 기준의 "17~18시" 표현을 Judge 가 "17시와 18시 두 슬롯"으로 읽어 맞는 답을 실패로 판정했다 → "17시 슬롯(17:00~18:00)"으로 문서·CSV·코드 표현을 통일
  - 회귀 평가 중 Bedrock 토큰 한도(ThrottlingException)로 Judge 가 판정을 돌려주지 못해 20건 중 8건이 Agent 실패처럼 기록됐다(12/20) → Judge 에 대기 시간을 늘리는 재시도와 Haiku 폴백을 넣고, 채점기 실패는 "판정 오류"로 따로 표시해 Agent 실패와 구분
  - 필수 안내(17시 전용 거절, 개인정보 거절)를 프롬프트로만 지시하면 폴백 모델이 답하거나 도구를 다르게 부를 때 빠졌다 → 도구 호출 방식이 아니라 질문 자체를 파이썬으로 판정해 누락 시 코드가 안내를 붙이도록 바꿈
- 최종 채택한 접근 · 왜 그것으로 갔는가
  - 정책은 프롬프트와 도구 양쪽에서 지킨다. create_reservation 이 수강증을 스스로 재검증해, 인젝션으로 모델이 속아도 17시 슬롯(17:00~18:00) 정기 회원 전용이 깨지지 않는다
  - 동시 예약은 "빈자리 확인 → 예약 번호 발급 → 저장"을 잠금 하나로 묶어 처리한다. 확인 직후 지연을 넣은 테스트로 수정 전에는 같은 슬롯 20건 동시 요청이 20건 모두 성공(이중 예약)하는 것을 재현했고, 수정 후에는 1건만 성공한다. 점검 닫기와 예약이 엇갈리는 경우도 같은 잠금으로 막았다
  - 계산·규칙 판정(회원 구분, 17시 슬롯 정책, 중복 예약, 없는 시설 번호)은 파이썬 코드로 하고, LLM 은 조회 순서 결정과 설명만 맡긴다. 프롬프트로 안 되던 10번이 바로 해결됐다
  - 한 번에 하나만 고치는 개선 루프(최대 3회): 무엇이 효과가 있었는지와 부작용을 문항 단위로 추적할 수 있었다. 효과 없는 변경은 되돌려 코드에 남기지 않았다
- 남은 한계 · 향후 개선 방향
  - 모델 출력이 확률적이라 같은 코드도 실행마다 결과가 흔들릴 수 있다(코드 보장 전 20/20·19/20) → 필수 안내는 코드로 보장하고, 평가는 반복 실행해 낮은 쪽을 보고한다
  - 평가셋 20건은 단일 질의만 다룬다. 실제 이용에서는 날짜 표현("내일", "이번 주 금요일")이 다양하므로 날짜 해석 문항을 늘릴 필요가 있다
  - 예약·점검 슬롯·대화 기록·만족도가 서버 메모리에만 있어 재시작하면 사라진다. 대화 기록에는 이용자가 입력한 원문(이름·전화번호)도 남는다 → 실제 운영 시 DB 연동, 보관 기간·마스킹 정책 필요
  - 동시 예약 잠금은 서버 프로세스 하나 안에서만 효과가 있다 → 서버를 여러 대 띄우거나 DB 로 옮기면 DB 고유 제약(날짜+시간+시설)·트랜잭션으로 같은 보장을 해야 한다
  - 관리자 화면은 메뉴로만 분리돼 있고 인증이 없다(데모용) → 운영 시 관리자 인증 필요

## 핵심 코드 위치
`src/` 는 업무 도메인별 폴더로 나뉜다 (배치 규칙: [CLAUDE.md](CLAUDE.md)). 제출 규약 경로 `src/agent.py`·`src/tools.py`·`src/retriever.py` 는 도메인 모듈을 다시 내보내는 진입점이다.
- `src/agent.py` — 메인 에이전트 진입점 → `src/assistant/`
  - `src/assistant/pipeline.py:102` — 메인 LCEL 체인 (guard_input → check_facilities → run_agent → build_response), `:49` 응답 구성·필수 안내 보장, `:37` 세션별 실행
  - `src/assistant/graph.py:30` — ReAct Agent 그래프 생성 (도구 4개 + 폴백·재시도·마스킹 미들웨어 + 체크포인터), `:20` 출력 PII 마스킹 미들웨어
  - `src/assistant/guardrails.py:19` — 입력 가드레일, `:36` 규칙 판정 단계(시설 번호·타인 예약 여부)
  - `src/assistant/prompts.py` — 시스템 프롬프트와 코드가 덧붙이는 안내 문구
- `src/tools.py` — 도메인 도구 진입점 → `src/reservation/` · `src/rules/`
  - `src/reservation/tools.py` — `check_membership:12`, `search_slots:19`, `create_reservation:26`
  - `src/reservation/service.py` — 동시 예약 잠금 `_STATE_LOCK:27`, 규칙 판정 `find_unknown_facilities:35`·`parse_slot_mention:55`·`mentions_member_only_hour:70`, 점검 슬롯 `close_slot:101`, 예약 확정 `reserve:213`
  - `src/rules/tools.py:10` — `retrieve_rules`
- `src/retriever.py` — RAG 진입점 → `src/rules/retriever.py:47` (`HybridRetriever`, BM25 + Titan 벡터 + RRF)
- `src/operations/dashboard.py:14` — 운영 집계, `src/operations/feedback.py:12` — 만족도 저장
- `src/web/server.py:27` — POST /query, `:21` GET / 웹 화면, 화면용 조회 API `/api/slots`·`/api/rules`, 관리자 API `/api/admin/*`
- `src/shared/` — 설정(`config.py`), Bedrock 클라이언트(`llm.py`), 마스킹(`pii.py`)
- `src/evaluation/runner.py` — 채점·RAGAS 계산 (Judge 재시도·폴백, 판정 오류 구분)
- `tests/test_reservation_concurrency.py` — 동시 예약 원자성 테스트
