"""채점 결과를 마크다운 리포트(roundN_report.md)로 만든다."""

import time
from collections import defaultdict
from pathlib import Path

from src.evaluation.metrics import JUDGE_MODEL_ID
from src.evaluation.schemas import CATEGORIES, RAGAS_METRICS, CaseResult
from src.shared.config import MODEL_ID


def mean(values) -> float | None:
    """None 을 뺀 평균."""
    vals = [v for v in values if v is not None]
    return sum(vals) / len(vals) if vals else None


def fmt(v) -> str:
    """점수 표시."""
    return "-" if v is None else f"{v:.2f}"


def write_report(results: list[CaseResult], round_no: int, path: Path) -> str:
    """채점 결과를 마크다운 리포트로 저장한다."""
    total = len(results)
    passed = sum(r["passed"] for r in results)
    by_cat = defaultdict(list)
    for r in results:
        by_cat[r["category"]].append(r)
    ragas = {m: mean(r["ragas"][m] for r in results) for m in RAGAS_METRICS}

    lines = [f"# {round_no}차 자체 평가 결과", "",
             f"- 평가 일시: {time.strftime('%Y-%m-%d %H:%M')}",
             f"- Agent 모델: {MODEL_ID} / Judge 모델: {JUDGE_MODEL_ID}",
             f"- 평가셋: evaluation/test_queries.csv ({total}건)", "",
             "## 인-아웃 세트 통과율", "",
             f"**전체: {passed} / {total} 통과 ({passed / total:.0%})**", ""]
    judge_errors = [r["id"] for r in results if r.get("judge_error")]
    if judge_errors:
        lines += [f"> ⚠️ 판정 오류 {len(judge_errors)}건 ({', '.join(judge_errors)}번): Judge 호출이 실패해 기대 항목을 판정하지 못했다. "
                  "Agent 실패가 아니므로 `--ids` 로 해당 문항을 재채점해야 한다.", ""]
    lines += ["| 카테고리 | 통과 | 비율 |", "|---|---|---|"]
    for cat in CATEGORIES:
        rs = by_cat.get(cat, [])
        if rs:
            p = sum(r["passed"] for r in rs)
            lines.append(f"| {cat} | {p} / {len(rs)} | {p / len(rs):.0%} |")
    lines += ["", "## RAGAS 지표 (RAGAS 정의 기반 LLM-as-Judge 계산)", "",
              "| 지표 | 점수 | 계산 대상 |", "|---|---|---|"]
    for m in RAGAS_METRICS:
        n = sum(r["ragas"][m] is not None for r in results)
        lines.append(f"| {m} | {fmt(ragas[m])} | {n}건 |")
    lines += ["", "> ragas 라이브러리가 Python 3.14 에서 설치되지 않아 같은 정의로 직접 구현했다. "
              "reference 는 expected_traits 를 쓴다. contexts 가 없는 문항은 context 지표에서 제외한다.", "",
              "## 문항별 결과", "",
              "| id | 분류 | 결과 | 호출 도구 | 실패 사유 |", "|---|---|---|---|---|"]
    for r in results:
        reasons = []
        if r["error"]:
            reasons.append(f"오류: {r['error'][:80]}")
        if r["missing_tools"]:
            reasons.append("도구 미호출: " + ", ".join(r["missing_tools"]))
        if r["forbidden_hits"]:
            reasons.append("금지어: " + ", ".join(r["forbidden_hits"]))
        if r["pii_leaks"]:
            reasons.append("PII 노출")
        if r.get("judge_error"):
            reasons.append("판정 오류 (재채점 필요): " + r["judge_error"][:80])
        if r["failed_traits"]:
            reasons.append("기대 미충족: " + ", ".join(map(str, r["failed_traits"])))
        mark = "✅" if r["passed"] else ("⚠️" if r.get("judge_error") else "❌")
        lines.append(f"| {r['id']} | {r['category']} | {mark} | {', '.join(r['called_tools']) or '-'} | "
                     f"{'<br>'.join(reasons).replace('|', '/') or '-'} |")
    lines += ["", "## 답변 원문 (사람 검토용)", ""]
    for r in results:
        lines += [f"### {r['id']}. [{r['category']}] {r['input']}", "",
                  f"- 기대 항목: " + "; ".join(t.get("trait", "") + (" ✅" if t.get("pass") else " ❌")
                                            for t in r["trait_results"]), "",
                  "```", r["answer"].strip() or "(빈 답변)", "```", ""]
    text = "\n".join(lines)
    path.write_text(text, encoding="utf-8")
    return text
