"""평가 도메인의 입출력 형식."""

from typing import TypedDict

RAGAS_METRICS = ["context_recall", "context_precision", "faithfulness", "answer_relevancy"]
CATEGORIES = ["positive", "negative", "edge", "guardrail"]


class CaseResult(TypedDict):
    """문항 하나의 채점 결과 (roundN_results.json 의 원소)."""
    id: str
    category: str
    input: str
    passed: bool
    checks: dict            # tools · forbidden · pii · traits · error
    judge_error: str
    missing_tools: list[str]
    forbidden_hits: list[str]
    pii_leaks: list[str]
    failed_traits: list[str]
    trait_results: list[dict]
    called_tools: list[str]
    answer: str
    error: str
    seconds: float
    ragas: dict             # RAGAS_METRICS 각 점수 (없으면 None)
