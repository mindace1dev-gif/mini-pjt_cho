"""이용 규정 도메인: data/center_rules.md 를 조항 단위로 하이브리드 검색(BM25 + 벡터, RRF)한다.

- retriever.py : 조항 분할·토큰화·하이브리드 검색기 (RAG 파이프라인)
- tools.py     : Agent 가 호출하는 retrieve_rules 도구
- prompts.py   : 도구 설명(LLM 에 전달)
- schemas.py   : 조항 검색 결과 형식
"""
