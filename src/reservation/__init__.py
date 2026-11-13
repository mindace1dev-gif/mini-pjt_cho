"""예약 도메인: 수강증(회원) 확인, 슬롯 조회, 예약 확정, 점검 슬롯, 시설·시간 규칙 판정.

- service.py : 상태(예약·점검)와 규칙 판정. 상태 변경은 _STATE_LOCK 안에서 "확인 → 확정"을 한 묶음으로 처리한다
- tools.py   : Agent 가 호출하는 LangChain 도구 (check_membership · search_slots · create_reservation)
- prompts.py : 도구 설명(LLM 에 전달)과 이용자 안내 문구
- schemas.py : 회원 구분 상수와 결과 형식
"""
