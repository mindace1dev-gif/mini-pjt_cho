"""공통 LLM 클라이언트: Bedrock 채팅 모델·폴백 모델·임베딩 생성."""

from langchain_aws import BedrockEmbeddings, ChatBedrockConverse

from src.shared.config import EMBEDDING_MODEL_ID, FALLBACK_MODEL_IDS, MODEL_ID


def chat_model(model_id: str = MODEL_ID) -> ChatBedrockConverse:
    """Bedrock 채팅 모델을 만든다 (temperature 0)."""
    return ChatBedrockConverse(model=model_id, temperature=0)


def fallback_models(model_ids: list[str] | None = None) -> list[ChatBedrockConverse]:
    """폴백 모델 목록을 만든다. 주 모델이 실패하면 이 순서대로 시도한다."""
    return [chat_model(m) for m in (FALLBACK_MODEL_IDS if model_ids is None else model_ids)]


def embeddings(model_id: str = EMBEDDING_MODEL_ID) -> BedrockEmbeddings:
    """Bedrock Titan 임베딩 클라이언트를 만든다."""
    return BedrockEmbeddings(model_id=model_id)
