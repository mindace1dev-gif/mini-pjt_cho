"""웹 도메인: POST /query API(제출 규약)와 이용자·관리자 화면, 화면용 조회 API.

- server.py         : FastAPI 앱과 라우트 (도메인 함수만 호출하고 규칙 판정은 하지 않는다)
- schemas.py        : 요청 본문 형식
- static/index.html : 웹 화면 (예약 · 시설 안내 · 이용 규정 · 관리자, 외부 라이브러리 없음)

실행: python -m uvicorn src.web.server:app --port 8000
"""
