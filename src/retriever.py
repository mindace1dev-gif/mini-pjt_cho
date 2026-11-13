"""[제출 규약 진입점] RAG 파이프라인 (센터 이용 규정 · BM25 + 벡터 하이브리드).

실제 구현은 src/rules/retriever.py 에 있다. 이 파일은 제출 규약 경로(src/retriever.py)를 지키기 위해 다시 내보내기만 한다.

실행: python src/retriever.py  (시험 질의 3개)
"""

import sys
from pathlib import Path

if __package__ in (None, ""):  # python src/retriever.py 로 직접 실행할 때 프로젝트 루트를 import 경로에 넣는다
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.rules.retriever import HybridRetriever, get_retriever, list_articles, load_articles, tokenize  # noqa: E402

__all__ = ["HybridRetriever", "get_retriever", "list_articles", "load_articles", "tokenize"]


if __name__ == "__main__":
    for q in ["정기 회원 전용 시간은 언제예요?", "만기된 수강증은 어떻게 해요?", "다른 사람 예약자 연락처"]:
        print(q, "→", [d.metadata["doc_id"] for d in get_retriever().search(q)])
