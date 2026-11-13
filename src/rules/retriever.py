"""센터 이용 규정 RAG 파이프라인 (BM25 + 벡터 하이브리드 검색)."""

import re
from functools import lru_cache
from pathlib import Path

from langchain_core.documents import Document
from langchain_core.vectorstores import InMemoryVectorStore
from rank_bm25 import BM25Okapi

from src.rules.schemas import RuleArticle
from src.shared.config import DATA_DIR
from src.shared.llm import embeddings as make_embeddings

RULES_PATH = DATA_DIR / "center_rules.md"
RRF_K = 60  # Reciprocal Rank Fusion 상수


def load_articles(path: Path = RULES_PATH) -> list[Document]:
    """규정 문서를 '## 제N조' 단위로 잘라 조항별 Document 로 만든다."""
    text = path.read_text(encoding="utf-8")
    docs = []
    for block in re.split(r"\n(?=## 제\d+조)", text):
        m = re.match(r"## (제\d+조) \((.+?)\)", block)
        if not m:
            continue
        article, title = m.group(1), m.group(2)
        docs.append(Document(page_content=block.strip(),
                             metadata={"doc_id": f"center_rules.md#{article}", "article": article, "title": title}))
    return docs


def list_articles() -> list[RuleArticle]:
    """화면용 조항 목록 (조항 번호·제목·본문). 규정 원문을 그대로 쓴다."""
    return [{"article": d.metadata["article"], "title": d.metadata["title"],
             "text": d.page_content.split("\n", 1)[1].strip() if "\n" in d.page_content else ""}
            for d in load_articles()]


def tokenize(text: str) -> list[str]:
    """한국어 BM25 용 토큰화. 어절과 글자 2-gram 을 함께 써 조사가 붙어도 매칭되게 한다."""
    words = re.findall(r"[0-9A-Za-z가-힣]+", text.lower())
    bigrams = [w[i:i + 2] for w in words for i in range(len(w) - 1)]
    return words + bigrams


class HybridRetriever:
    """BM25 키워드 검색과 Titan 벡터 검색 결과를 RRF 로 합친다."""

    def __init__(self, docs: list[Document], embeddings=None):
        """조항 문서로 두 인덱스를 만든다."""
        self.docs = docs
        self.bm25 = BM25Okapi([tokenize(d.page_content) for d in docs])
        self.vectors = InMemoryVectorStore(embeddings or make_embeddings())
        self.vectors.add_documents(docs, ids=[d.metadata["doc_id"] for d in docs])

    def search(self, query: str, k: int = 3) -> list[Document]:
        """질의와 관련 있는 조항을 최대 k 개 돌려준다."""
        n = len(self.docs)
        scores = self.bm25.get_scores(tokenize(query))
        bm25_rank = [self.docs[i].metadata["doc_id"] for i in sorted(range(n), key=lambda i: -scores[i])
                     if scores[i] > 0]
        vector_rank = [d.metadata["doc_id"] for d in self.vectors.similarity_search(query, k=n)]

        fused: dict[str, float] = {}
        for ranking in (bm25_rank, vector_rank):
            for rank, doc_id in enumerate(ranking):
                fused[doc_id] = fused.get(doc_id, 0.0) + 1.0 / (RRF_K + rank + 1)
        by_id = {d.metadata["doc_id"]: d for d in self.docs}
        top = sorted(fused, key=lambda d: -fused[d])[:k]
        return [by_id[d] for d in top]


@lru_cache(maxsize=1)
def get_retriever() -> HybridRetriever:
    """규정 검색기를 한 번만 만들어 재사용한다."""
    return HybridRetriever(load_articles())
