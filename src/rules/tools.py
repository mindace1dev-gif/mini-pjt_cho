"""이용 규정 도메인의 Agent 도구."""

from langchain_core.tools import tool

from src.rules.prompts import RETRIEVE_RULES_DESCRIPTION
from src.rules.retriever import get_retriever


@tool(description=RETRIEVE_RULES_DESCRIPTION)
def retrieve_rules(query: str) -> list[dict]:
    """센터 이용 규정에서 질문과 관련된 조항을 찾는다."""
    return [{"doc_id": d.metadata["doc_id"], "article": d.metadata["article"], "text": d.page_content}
            for d in get_retriever().search(query)]


RULES_TOOLS = [retrieve_rules]
