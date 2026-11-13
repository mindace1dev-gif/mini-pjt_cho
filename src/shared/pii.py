"""개인정보(이름·전화번호) 마스킹과 마스킹 대상 이름 목록."""

import re

from src.shared.config import load_json

PHONE_PATTERN = re.compile(r"01[016789]-?\d{3,4}-?(\d{4})")


def mask_name(name: str) -> str:
    """이름의 가운데 글자를 가린다. 예: 김민수 → 김*수, 홍길 → 홍*"""
    if not name:
        return name
    if len(name) <= 2:
        return name[0] + "*"
    return name[0] + "*" * (len(name) - 2) + name[-1]


def mask_phone(phone: str) -> str:
    """전화번호의 가운데 자리를 가린다. 예: 010-1234-5678 → 010-****-5678"""
    if not phone:
        return phone
    return PHONE_PATTERN.sub(lambda m: f"{m.group(0)[:3]}-****-{m.group(1)}", phone)


def mask_text(text: str, names: list[str] | None = None) -> str:
    """문장 속 전화번호와 알려진 이름을 모두 가린다."""
    if not text:
        return text
    masked = mask_phone(text)
    for name in sorted(set(names or []), key=len, reverse=True):
        if name:
            masked = masked.replace(name, mask_name(name))
    return masked


def known_names() -> list[str]:
    """마스킹 대상 이름 목록 (회원 명단 + 예약자)."""
    members = load_json("members.json")["members"]
    slots = load_json("slots.json")
    return [m["name"] for m in members] + [r["name"] for r in slots["reservations"] if r.get("name")]


KNOWN_NAMES = known_names()
