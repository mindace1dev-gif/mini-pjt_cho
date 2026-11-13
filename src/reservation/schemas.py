"""예약 도메인의 상수와 입출력 형식."""

from typing import TypedDict

MEMBER = "정기 회원"
GUEST = "일반인"


class MembershipResult(TypedDict, total=False):
    """수강증 확인 결과."""
    member_type: str      # 정기 회원 / 일반인
    verified: bool
    reason: str
    card_no: str
    name: str             # 가려진 이름
    expires_at: str


class SlotEntry(TypedDict, total=False):
    """한 시간대의 예약 가능 현황."""
    hour: int
    available: list[str]                # 예약 가능한 시설 ID
    closed_for_maintenance: list[str]   # 점검으로 닫힌 시설 ID
    note: str


class ReservationResult(TypedDict, total=False):
    """예약 시도 결과."""
    reserved: bool
    reason: str
    reservation: dict
    membership: MembershipResult


class UnknownFacility(TypedDict):
    """센터에 없는 시설 번호 판정 결과."""
    facility: str   # 예: 배팅케이지 6번
    message: str    # 이용자 안내 문장


class SlotMention(TypedDict):
    """문장에서 읽어 낸 슬롯."""
    date: str
    hour: int
    facility_id: str
    facility_name: str
