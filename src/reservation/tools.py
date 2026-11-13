"""예약 도메인의 Agent 도구. 실제 판정은 service.py 가 하고, 여기서는 도구 형식으로 감싸기만 한다."""

from langchain_core.tools import tool

from src.reservation import service
from src.reservation.prompts import (CHECK_MEMBERSHIP_DESCRIPTION, CREATE_RESERVATION_DESCRIPTION,
                                     SEARCH_SLOTS_DESCRIPTION)
from src.reservation.schemas import GUEST


@tool(description=CHECK_MEMBERSHIP_DESCRIPTION)
def check_membership(card_no: str | None = None, name: str | None = None,
                     phone: str | None = None, qr: str | None = None) -> dict:
    """수강증으로 정기 회원 여부를 확인한다."""
    return service.verify_membership(card_no, name, phone, qr)


@tool(description=SEARCH_SLOTS_DESCRIPTION)
def search_slots(date: str, hour: int | None = None, facility_type: str | None = None,
                 facility_id: str | None = None, member_type: str = GUEST) -> dict:
    """날짜·시간·시설 조건에 맞는 예약 가능 슬롯을 조회한다."""
    return service.find_slots(date, hour, facility_type, facility_id, member_type)


@tool(description=CREATE_RESERVATION_DESCRIPTION)
def create_reservation(date: str, hour: int, facility_id: str, card_no: str | None = None) -> dict:
    """선택한 슬롯을 예약한다."""
    return service.reserve(date, hour, facility_id, card_no)


RESERVATION_TOOLS = [check_membership, search_slots, create_reservation]
