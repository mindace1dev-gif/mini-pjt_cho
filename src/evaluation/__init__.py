"""품질 평가 도메인: evaluation/test_queries.csv 로 Agent 를 실행·채점하고 리포트를 만든다.

채점 규칙 (모두 만족해야 통과)
- expected_tools: 적힌 도구를 모두 호출했는가
- forbidden: 금지 항목이 answer 에 없는가
- PII: 응답 전체(answer·contexts·trace)에 가려지지 않은 전화번호가 없는가
- expected_traits: LLM-as-Judge 가 항목마다 충족 여부를 판정

RAGAS 지표 4개는 RAGAS 정의를 따라 LLM-as-Judge 로 계산한다.
(ragas 라이브러리가 Python 3.14 환경에서 설치되지 않아 같은 정의로 직접 구현)

- runner.py  : 실행 진입점 (python -m src.evaluation.runner --round 2)
- metrics.py : Judge 호출(재시도·폴백, 판정 오류 구분)과 RAGAS 지표 계산
- report.py  : roundN_report.md 작성
- prompts.py : Judge·질문 역생성 프롬프트
- schemas.py : 문항 결과 형식

평가셋과 결과 리포트는 제출 규약대로 루트 evaluation/ 폴더에 둔다.
"""
