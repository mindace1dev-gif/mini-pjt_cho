"""이용 규정 도메인의 입출력 형식."""

from typing import TypedDict


class RuleHit(TypedDict):
    """retrieve_rules 가 돌려주는 조항 하나."""
    doc_id: str     # 예: center_rules.md#제6조
    article: str    # 예: 제6조
    text: str       # 조항 본문


class RuleArticle(TypedDict):
    """화면용 규정 조항 (GET /api/rules)."""
    article: str
    title: str
    text: str
