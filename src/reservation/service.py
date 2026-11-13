"""예약 도메인 실행 로직: 회원 확인, 슬롯 조회, 예약 확정, 점검 슬롯, 시설·시간 규칙 판정.

계산·규칙 판정은 모두 여기서 파이썬으로 한다 (LLM 에 맡기지 않는다).
"""

import re
import threading
from datetime import date

from src.reservation.prompts import MEMBER_ONLY_NOTE, MEMBER_ONLY_REASON, UNKNOWN_FACILITY_MESSAGE
from src.reservation.schemas import (GUEST, MEMBER, MembershipResult, ReservationResult, SlotMention,
                                     UnknownFacility)
from src.shared.config import load_json
from src.shared.pii import mask_name

_MEMBERS = load_json("members.json")["members"]
_SLOTS = load_json("slots.json")
_FACILITIES = {f["facility_id"]: f for f in _SLOTS["facilities"]}
_FACILITY_TYPES = sorted({f["type"] for f in _SLOTS["facilities"]})
_MEMBER_ONLY_HOURS = set(_SLOTS["rules"]["member_only_hours"])
# 예약 현황은 메모리에서만 갱신한다. 원본 JSON 은 바꾸지 않아 평가를 반복해도 같은 상태에서 시작한다.
_RESERVATIONS = list(_SLOTS["reservations"])
# 관리자가 점검으로 닫은 슬롯 {(날짜, 시간, 시설 ID): 사유}. 메모리에서만 관리한다.
_CLOSURES: dict[tuple[str, int, str], str] = {}
# 예약·점검 상태를 바꾸는 작업은 "확인 → 확정"을 이 잠금 안에서 한 묶음으로 처리한다.
# 서버는 요청을 여러 스레드로 동시에 처리하므로, 잠금이 없으면 두 요청이 같은 빈자리를 동시에 확인하고 둘 다 예약할 수 있다.
_STATE_LOCK = threading.RLock()


_FACILITY_MENTION = re.compile(r"(배팅\s*케이지|피칭\s*머신)\s*(\d+)\s*번|\b(BC|PM)-(\d+)\b", re.IGNORECASE)
_FACILITY_PREFIX = {"배팅케이지": "BC", "피칭머신": "PM", "BC": "BC", "PM": "PM"}
_PREFIX_NAME = {"BC": "배팅케이지", "PM": "피칭머신"}


def find_unknown_facilities(text: str) -> list[UnknownFacility]:
    """[규칙 판정] 문장에서 시설 번호를 찾아, 센터에 없는 번호면 안내 문장을 돌려준다.

    예: '배팅케이지 6번' → [{"facility": "배팅케이지 6번", "message": "배팅케이지 6번은 없는 시설입니다. ..."}]
    """
    found = []
    for m in _FACILITY_MENTION.finditer(text or ""):
        kind = re.sub(r"\s", "", m.group(1)) if m.group(1) else m.group(3).upper()
        number = int(m.group(2) or m.group(4))
        prefix = _FACILITY_PREFIX[kind]
        if f"{prefix}-{number}" in _FACILITIES:
            continue
        name = _PREFIX_NAME[prefix]
        limit = sum(1 for f in _FACILITIES if f.startswith(prefix + "-"))
        topic = "은" if (ord(name[-1]) - 0xAC00) % 28 else "는"  # 받침 유무로 조사 선택
        found.append({"facility": f"{name} {number}번",
                      "message": UNKNOWN_FACILITY_MESSAGE.format(name=name, number=number, topic=topic, limit=limit)})
    return found


def parse_slot_mention(text: str) -> SlotMention | None:
    """[규칙 판정] 문장에서 '날짜(YYYY-MM-DD) · 시간(N시) · 시설 번호'가 모두 있으면 슬롯으로 읽는다. 하나라도 없으면 None."""
    day = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", text or "")
    hour = re.search(r"(?<!\d)(\d{1,2})\s*시", text or "")
    fac = _FACILITY_MENTION.search(text or "")
    if not (day and hour and fac):
        return None
    kind = re.sub(r"\s", "", fac.group(1)) if fac.group(1) else fac.group(3).upper()
    facility_id = f"{_FACILITY_PREFIX[kind]}-{int(fac.group(2) or fac.group(4))}"
    if facility_id not in _FACILITIES or not 0 <= int(hour.group(1)) <= 23:
        return None
    return {"date": day.group(1), "hour": int(hour.group(1)), "facility_id": facility_id,
            "facility_name": _FACILITIES[facility_id]["name"]}


def mentions_member_only_hour(text: str) -> bool:
    """[규칙 판정] 문장이 정기 회원 전용 시간(17시 = 오후 5시)을 요청하는지 본다."""
    for hour in _MEMBER_ONLY_HOURS:
        patterns = [rf"(?<!\d){hour}\s*시", rf"{hour}:00"]
        if hour > 12:
            patterns.append(rf"(오후|저녁)\s*{hour - 12}\s*시")
        if any(re.search(p, text or "") for p in patterns):
            return True
    return False


def reset_reservations() -> None:
    """예약 현황과 점검 슬롯을 원본 상태로 되돌린다. 평가에서 문항마다 같은 상태로 시작하기 위해 쓴다."""
    with _STATE_LOCK:
        _RESERVATIONS[:] = list(_SLOTS["reservations"])
        _CLOSURES.clear()


def reservations_snapshot() -> list[dict]:
    """현재 예약 목록 (개인정보 제외: 날짜·시간·시설·회원 구분만)."""
    with _STATE_LOCK:
        return [{k: r[k] for k in ("date", "hour", "facility_id", "member_type")} for r in _RESERVATIONS]


def list_closures() -> list[dict]:
    """점검으로 닫힌 슬롯 목록."""
    with _STATE_LOCK:
        return [{"date": d, "hour": h, "facility_id": f, "reason": reason}
                for (d, h, f), reason in sorted(_CLOSURES.items())]


def close_slot(date: str, hour: int, facility_id: str, reason: str = "시설 점검") -> dict:
    """[관리자] 슬롯을 점검으로 닫는다. 예약이 있는 슬롯은 닫지 않는다(알림 기능이 없어 예약자에게 알릴 수 없음)."""
    facility_id = (facility_id or "").upper()
    if _parse_date(date) is None or not 0 <= int(hour) <= 23:
        return {"ok": False, "reason": "날짜(YYYY-MM-DD)·시간(0~23)을 확인하세요"}
    if facility_id not in _FACILITIES:
        return {"ok": False, "reason": "없는 시설 번호"}
    with _STATE_LOCK:  # 예약 여부 확인과 닫기를 한 묶음으로 (동시에 들어온 예약과 엇갈리지 않게)
        if facility_id in _taken(date, int(hour)):
            return {"ok": False, "reason": "이미 예약이 있는 슬롯은 닫을 수 없음"}
        _CLOSURES[(date, int(hour), facility_id)] = (reason or "시설 점검").strip()[:50]
        return {"ok": True, "closed": list_closures()}


def open_slot(date: str, hour: int, facility_id: str) -> dict:
    """[관리자] 점검으로 닫은 슬롯을 다시 연다."""
    with _STATE_LOCK:
        removed = _CLOSURES.pop((date, int(hour), (facility_id or "").upper()), None)
        return {"ok": removed is not None, "reason": "" if removed is not None else "닫힌 슬롯이 아님",
                "closed": list_closures()}


def _digits(text: str | None) -> str:
    """숫자만 남긴다. 전화번호 비교용."""
    return re.sub(r"\D", "", text or "")


def _today() -> date:
    """오늘 날짜. 만기일 판정 기준."""
    return date.today()


def verify_membership(card_no=None, name=None, phone=None, qr=None) -> MembershipResult:
    """수강증을 확인해 회원 구분과 사유를 돌려준다. 개인정보는 가린다."""
    member = None
    if card_no:
        member = next((m for m in _MEMBERS if m["card_no"] == card_no.strip().upper()), None)
        if not member:
            return {"member_type": GUEST, "verified": False, "reason": "명단에 없는 수강증 번호"}
    elif qr:
        member = next((m for m in _MEMBERS if m["qr"] == qr.strip().upper()), None)
        if not member:
            return {"member_type": GUEST, "verified": False, "reason": "명단에 없는 QR"}
    elif name or phone:
        if not (name and phone):
            return {"member_type": GUEST, "verified": False,
                    "reason": "이름과 전화번호가 모두 있어야 확인할 수 있음"}
        member = next((m for m in _MEMBERS
                       if m["name"] == name.strip() and _digits(m["phone"]) == _digits(phone)), None)
        if not member:
            return {"member_type": GUEST, "verified": False, "reason": "이름과 전화번호가 일치하는 회원 없음"}
    else:
        return {"member_type": GUEST, "verified": False, "reason": "수강증 정보가 입력되지 않음"}

    result = {"card_no": member["card_no"], "name": mask_name(member["name"]),
              "expires_at": member["expires_at"]}
    if date.fromisoformat(member["expires_at"]) < _today():
        return {**result, "member_type": GUEST, "verified": False, "reason": "수강증 만기일이 지남"}
    return {**result, "member_type": MEMBER, "verified": True, "reason": "유효한 수강증"}


def _parse_date(value: str) -> date | None:
    """YYYY-MM-DD 문자열을 날짜로 바꾼다. 형식이 틀리면 None."""
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def _taken(day: str, hour: int) -> set[str]:
    """해당 날짜·시간에 이미 예약된 시설 ID 목록."""
    return {r["facility_id"] for r in _RESERVATIONS if r["date"] == day and r["hour"] == hour}


def find_slots(date: str, hour: int | None = None, facility_type: str | None = None,
               facility_id: str | None = None, member_type: str = GUEST) -> dict:
    """날짜·시간·시설 조건에 맞는 예약 가능 슬롯을 조회한다. 예약자 정보는 담지 않는다."""
    if _parse_date(date) is None:
        return {"ok": False, "reason": "날짜 형식이 올바르지 않음 (YYYY-MM-DD)"}
    if hour is not None and not 0 <= hour <= 23:
        return {"ok": False, "reason": "시간은 0~23 사이여야 함"}
    if facility_type and facility_type not in _FACILITY_TYPES:
        return {"ok": False, "reason": f"제공하지 않는 시설. 예약 가능 시설: {', '.join(_FACILITY_TYPES)}"}
    if facility_id and facility_id.upper() not in _FACILITIES:
        return {"ok": False, "reason": "없는 시설 번호. 배팅케이지 BC-1~BC-5, 피칭머신 PM-1~PM-10 만 있음"}

    candidates = [f for f in _SLOTS["facilities"]
                  if (not facility_type or f["type"] == facility_type)
                  and (not facility_id or f["facility_id"] == facility_id.upper())]
    results = []
    for h in ([hour] if hour is not None else range(24)):
        if h in _MEMBER_ONLY_HOURS and member_type != MEMBER:
            results.append({"hour": h, "available": [], "note": MEMBER_ONLY_NOTE})
            continue
        taken = _taken(date, h)
        closed = [f["facility_id"] for f in candidates if (date, h, f["facility_id"]) in _CLOSURES]
        free = [f["facility_id"] for f in candidates if f["facility_id"] not in taken and f["facility_id"] not in closed]
        entry = {"hour": h, "available": free}
        if closed:
            entry["closed_for_maintenance"] = closed
        if not free:
            reserved_here = taken & {c["facility_id"] for c in candidates}
            if closed and not reserved_here:
                entry["note"] = "점검 중"
            elif closed:
                entry["note"] = "만석 (일부 점검 중)"
            else:
                entry["note"] = "만석"
        results.append(entry)
    return {"ok": True, "date": date, "member_type": member_type, "slots": results}


def reserve(date: str, hour: int, facility_id: str, card_no: str | None = None) -> ReservationResult:
    """선택한 슬롯을 예약한다. 수강증을 다시 확인하고, 정기 회원 전용·중복·점검·없는 시설을 판정한다."""
    if _parse_date(date) is None:
        return {"reserved": False, "reason": "날짜 형식이 올바르지 않음 (YYYY-MM-DD)"}
    if not 0 <= hour <= 23:
        return {"reserved": False, "reason": "시간은 0~23 사이여야 함"}
    facility_id = (facility_id or "").upper()
    if facility_id not in _FACILITIES:
        return {"reserved": False, "reason": "없는 시설 번호. 배팅케이지 BC-1~BC-5, 피칭머신 PM-1~PM-10 만 있음"}

    member = verify_membership(card_no=card_no) if card_no else {"member_type": GUEST, "verified": False}
    if hour in _MEMBER_ONLY_HOURS and not member["verified"]:
        return {"reserved": False, "reason": MEMBER_ONLY_REASON, "membership": member}
    # 빈자리·점검 확인 → 예약 번호 발급 → 저장을 한 묶음으로 처리한다. 같은 슬롯에 동시 요청이 와도 한 건만 성공한다.
    with _STATE_LOCK:
        if facility_id in _taken(date, hour):
            return {"reserved": False, "reason": "이미 예약된 슬롯"}
        if (date, hour, facility_id) in _CLOSURES:
            return {"reserved": False, "reason": f"점검으로 닫힌 슬롯 ({_CLOSURES[(date, hour, facility_id)]})"}
        reservation = {"reservation_id": f"R-{len(_RESERVATIONS) + 1:04d}", "date": date, "hour": hour,
                       "facility_id": facility_id, "member_type": member["member_type"],
                       "card_no": member.get("card_no") if member["verified"] else None}
        _RESERVATIONS.append(reservation)
    return {"reserved": True, "reason": "예약 완료",
            "reservation": {**reservation, "facility_name": _FACILITIES[facility_id]["name"]}}
