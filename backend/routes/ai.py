"""AI assistant API (phase 8): constrained Q&A over one batch.

Read-only. The agent answers strictly from backend tools; if the batch is
unknown the endpoint returns the standard structured 404 like every other
resource route.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.ai_agent import AIProvider, answer_question
from backend.ai_provider_groq import build_groq_provider_from_env
from backend.database import Database
from backend.repositories import BatchRepository
from backend.routes.batches import get_database
from backend.schemas import ErrorResponse

router = APIRouter(prefix="/api/v1/ai", tags=["ai"])


def get_ai_provider() -> AIProvider:
    """Provider factory — groq when SETTLESENSE_AI_PROVIDER=groq AND a key
    is configured (server-side env/.env only); otherwise the deterministic
    pass-through provider. Absence of a model is a supported state."""
    return build_groq_provider_from_env() or AIProvider()


class AIQueryRequest(BaseModel):
    batch_id: str = Field(min_length=1)
    question: str = Field(min_length=1, max_length=2000)


class AIQueryResponse(BaseModel):
    answer: str
    record_ids: list[str] = []
    tools_used: list[str] = []
    requires_review: bool = True
    fallback: bool = False
    provider: str = "none"  # which layer served the answer: none | groq


@router.post(
    "/query",
    response_model=AIQueryResponse,
    responses={
        404: {"model": ErrorResponse, "description": "unknown batch"},
        422: {"model": ErrorResponse, "description": "invalid request"},
    },
)
def ai_query(
    request: AIQueryRequest,
    db: Database = Depends(get_database),
    provider: AIProvider = Depends(get_ai_provider),
) -> AIQueryResponse:
    conn = db.connect(init=False)
    try:
        if BatchRepository(conn).find_by_id(request.batch_id) is None:
            raise HTTPException(404, detail={
                "code": "batch_not_found",
                "message": f"no batch with id {request.batch_id!r}"})
    finally:
        conn.close()

    result = answer_question(
        request.batch_id, request.question, db, provider=provider)
    return AIQueryResponse(**result.to_dict(), provider=provider.name)
