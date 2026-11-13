"""공통 설정: 프로젝트 경로, .env 로드, 모델 ID, 데이터 파일 읽기."""

import json
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
load_dotenv(ROOT / ".env")

# 주 모델과, 주 모델이 실패하면 순서대로 시도할 폴백 모델 (.env 로 변경, 쉼표 구분)
MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-6")
FALLBACK_MODEL_IDS = [m.strip() for m in os.getenv(
    "BEDROCK_FALLBACK_MODEL_IDS",
    "us.anthropic.claude-haiku-4-5-20251001-v1:0,global.anthropic.claude-sonnet-4-6",
).split(",") if m.strip()]
EMBEDDING_MODEL_ID = os.getenv("BEDROCK_EMBEDDING_MODEL_ID", "amazon.titan-embed-text-v2:0")


def load_json(name: str) -> dict:
    """data 폴더의 JSON 파일을 읽는다."""
    with open(DATA_DIR / name, encoding="utf-8") as f:
        return json.load(f)
