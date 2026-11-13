"""평가 실행 진입점: test_queries.csv 의 문항마다 Agent 를 실행하고 채점한다.

사용법: python -m src.evaluation.runner --round 2 [--ids 1,3,9] [--out-dir 폴더]
"""

import argparse
import csv
import json
import re
import time
from pathlib import Path

from src.assistant.pipeline import answer_question
from src.evaluation.metrics import JUDGE_MODEL_ID, answer_relevancy, judge, ragas_scores
from src.evaluation.report import write_report
from src.evaluation.schemas import CaseResult
from src.reservation.service import reset_reservations
from src.shared.config import ROOT
from src.shared.llm import chat_model, embeddings

EVAL_DIR = ROOT / "evaluation"
CSV_PATH = EVAL_DIR / "test_queries.csv"
FULL_PHONE = re.compile(r"01[016789]-?(?!\*)\d{3,4}-?\d{4}")


def split(cell: str) -> list[str]:
    """세미콜론으로 구분된 칸을 목록으로 바꾼다."""
    return [x.strip() for x in (cell or "").split(";") if x.strip()]


def evaluate_case(row: dict, llm, emb) -> CaseResult:
    """문항 하나를 실행하고 채점한다."""
    reset_reservations()
    started = time.time()
    try:
        res = answer_question(row["input"])
        error = ""
    except Exception as e:
        res, error = {"answer": "", "contexts": [], "trace": []}, f"{type(e).__name__}: {e}"
    elapsed = time.time() - started

    answer = res["answer"]
    called = [t["step"].split(":", 1)[1] if t["step"].startswith("tool:") else "retrieve_rules"
              for t in res["trace"] if t["step"].startswith(("tool:", "retrieve"))]
    missing_tools = [t for t in split(row["expected_tools"]) if t not in called]
    forbidden_hits = [f for f in split(row["forbidden"]) if f in answer]
    pii_leaks = FULL_PHONE.findall(json.dumps(res, ensure_ascii=False))

    traits = split(row["expected_traits"])
    verdict = judge(llm, row["input"], answer, res["contexts"], traits)
    trait_results = verdict.get("traits") or []
    judge_error = verdict.get("judge_error", "")
    failed_traits = [t.get("trait") for t in trait_results if not t.get("pass")]
    if len(trait_results) < len(traits) and not judge_error:
        failed_traits.append("(판정 누락)")

    # Judge 가 실패하면 기대 항목을 판정할 수 없으므로 통과로 세지 않고 '판정 오류'로 따로 표시한다
    checks = {"tools": not missing_tools, "forbidden": not forbidden_hits,
              "pii": not pii_leaks, "traits": not failed_traits and not judge_error, "error": not error}
    return {
        "id": row["id"], "category": row["category"], "input": row["input"],
        "passed": all(checks.values()), "checks": checks, "judge_error": judge_error,
        "missing_tools": missing_tools, "forbidden_hits": forbidden_hits, "pii_leaks": pii_leaks,
        "failed_traits": failed_traits, "trait_results": trait_results,
        "called_tools": called, "answer": answer, "error": error, "seconds": round(elapsed, 1),
        "ragas": {**ragas_scores(verdict, bool(res["contexts"])),
                  "answer_relevancy": answer_relevancy(llm, emb, row["input"], answer)},
    }


def main():
    """평가를 실행한다."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--round", type=int, default=1)
    parser.add_argument("--ids", default="", help="일부 문항만: 1,3,9")
    parser.add_argument("--out-dir", default=str(EVAL_DIR), help="결과 저장 폴더 (개선 루프 중간 결과용)")
    args = parser.parse_args()

    rows = list(csv.DictReader(open(CSV_PATH, encoding="utf-8", newline="")))
    if args.ids:
        wanted = set(args.ids.split(","))
        rows = [r for r in rows if r["id"] in wanted]
    llm = chat_model(JUDGE_MODEL_ID)
    emb = embeddings()

    results = []
    for row in rows:
        r = evaluate_case(row, llm, emb)
        results.append(r)
        print(f"[{r['id']:>2}] {r['category']:<9} {'PASS' if r['passed'] else 'FAIL'} "
              f"{r['seconds']:>5}s  {r['checks']}", flush=True)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    suffix = "" if not args.ids else "_partial"
    (out_dir / f"round{args.round}_results{suffix}.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    report = write_report(results, args.round, out_dir / f"round{args.round}_report{suffix}.md")
    print("\n" + "\n".join(report.splitlines()[:30]))


if __name__ == "__main__":
    main()
