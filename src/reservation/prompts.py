"""예약 도메인의 프롬프트(도구 설명)와 이용자 안내 문구."""

CHECK_MEMBERSHIP_DESCRIPTION = """수강증으로 정기 회원 여부를 확인한다.

수강증 번호(card_no, 예: M-1001), 이름+전화번호(name, phone), QR 값(qr, 예: QR-M1001) 중 하나로 조회한다.
명단에 없거나, 만기일이 지났거나, 이름과 전화번호가 일치하지 않으면 정기 회원으로 인정하지 않고 일반인으로 판정한다.
반환: member_type(정기 회원/일반인), verified, reason, card_no, 가려진 name, expires_at."""

SEARCH_SLOTS_DESCRIPTION = """날짜·시간·시설 조건에 맞는 예약 가능 슬롯을 조회한다.

date 는 YYYY-MM-DD, hour 는 0~23 (17 은 17:00~18:00 슬롯). hour 를 비우면 그날 전체 시간을 본다.
facility_type 은 '배팅케이지' 또는 '피칭머신', facility_id 는 BC-1~BC-5, PM-1~PM-10.
member_type 은 '정기 회원' 또는 '일반인'. 17시 슬롯은 정기 회원 전용이라 일반인에게는 비어 있어도 보여주지 않는다.
반환: 시간별 예약 가능 시설 목록과 예약 불가 사유. 예약자 정보는 담지 않는다."""

CREATE_RESERVATION_DESCRIPTION = """선택한 슬롯을 예약한다.

date 는 YYYY-MM-DD, hour 는 0~23, facility_id 는 BC-1~BC-5 또는 PM-1~PM-10.
정기 회원이면 card_no(수강증 번호)를 넘긴다. 도구가 수강증을 다시 확인하며, 없으면 일반인으로 예약한다.
17시 슬롯은 확인된 정기 회원만 예약할 수 있다. 이미 예약된 슬롯이나 없는 시설은 예약하지 않는다.
반환: reserved(예약 성공 여부), reason, 예약 정보."""

# 이용자 안내 문구 (규칙 판정 결과)
UNKNOWN_FACILITY_MESSAGE = "{name} {number}번은 없는 시설입니다. {name}{topic} 1~{limit}번만 있습니다."
MEMBER_ONLY_REASON = "17시 슬롯(17:00~18:00)은 정기 회원 전용 시간 (유효한 수강증 필요)"
MEMBER_ONLY_NOTE = "정기 회원 전용 시간 (일반인 예약 불가)"
