"""LLM-as-Judge 호출과 RAGAS 정의 기반 지표 계산."""

import json
import math
import os
import re
import time

from src.evaluation.prompts import JUDGE_PROMPT, QUESTION_GEN_PROMPT
from src.shared.llm import chat_model

JUDGE_MODEL_ID = os.getenv("JUDGE_MODEL_ID", "us.anthropic.claude-sonnet-4-6")
JUDGE_FALLBACK_MODEL_IDS = [m for m in os.getenv(
    "JUDGE_FALLBACK_MODEL_IDS", "us.anthropic.claude-haiku-4-5-20251001-v1:0").split(",") if m.strip()]
JUDGE_FALLBACKS = [chat_model(m) for m in JUDGE_FALLBACK_MODEL_IDS]


def extract_json(text: str):
    """모델 출력에서 JSON 부분만 읽는다."""
    m = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
    return json.loads(m.group(1)) if m else None


def judge(llm, question: str, answer: str, contexts: list[dict], traits: list[str]) -> dict:
    """LLM-as-Judge 로 기대 항목과 RAGAS 판정 재료를 받는다."""
    ctx_text = "\n".join(f"{i + 1}. [{c['doc_id']}] {c['text'][:800]}" for i, c in enumerate(contexts)) or "(없음)"
    prompt = JUDGE_PROMPT.format(question=question, answer=answer, contexts=ctx_text,
                                 traits="\n".join(f"- {t}" for t in traits))
    error = ""
    for model in [llm] + JUDGE_FALLBACKS:  # 주 Judge 가 끝내 실패하면 폴백 모델로 넘어간다
        for attempt in range(3):
            try:
                data = extract_json(model.invoke(prompt).text)
                if isinstance(data, dict):
                    return data
                error = "Judge 출력에서 JSON 을 찾지 못함"
            except Exception as e:  # 호출 제한·지연·파싱 실패 시 대기 시간을 늘려 재시도
                error = f"{type(e).__name__}: {str(e)[:120]}"
                print("  judge 재시도:", error, flush=True)
            time.sleep(2 ** (attempt + 1))
    # 채점기 실패는 Agent 실패와 구분해 기록한다 (리포트에 '판정 오류'로 표시)
    return {"traits": [], "claims": [], "context_relevance": [], "reference_support": [], "judge_error": error}


def cosine(a: list[float], b: list[float]) -> float:
    """두 벡터의 코사인 유사도."""
    dot = sum(x * y for x, y in zip(a, b))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)) or 1.0)


def answer_relevancy(llm, emb, question: str, answer: str) -> float | None:
    """RAGAS answer_relevancy: 답변에서 역생성한 질문과 원 질문의 유사도 평균."""
    if not answer.strip():
        return None
    try:
        questions = extract_json(llm.invoke(QUESTION_GEN_PROMPT.format(answer=answer)).text) or []
    except Exception:
        return None
    if not questions:
        return None
    q_vec = emb.embed_query(question)
    return sum(cosine(q_vec, v) for v in emb.embed_documents(questions)) / len(questions)


def ragas_scores(verdict: dict, has_contexts: bool) -> dict:
    """판정 결과로 faithfulness·context_precision·context_recall 을 계산한다. 근거가 없으면 None."""
    if not has_contexts:
        return {"faithfulness": None, "context_precision": None, "context_recall": None}
    claims = verdict.get("claims") or []
    faith = sum(bool(c.get("supported")) for c in claims) / len(claims) if claims else None
    rel = [bool(x) for x in verdict.get("context_relevance") or []]
    if any(rel):
        hits, precisions = 0, []
        for k, r in enumerate(rel, 1):
            if r:
                hits += 1
                precisions.append(hits / k)
        precision = sum(precisions) / hits
    else:
        precision = 0.0 if rel else None
    sup = [bool(x) for x in verdict.get("reference_support") or []]
    recall = sum(sup) / len(sup) if sup else None
    return {"faithfulness": faith, "context_precision": precision, "context_recall": recall}
