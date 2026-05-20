from fastapi import APIRouter, HTTPException

from app.core.config import settings
from app.schemas.chat_schema import ChatRequest, ChatResponse, EvidenceItem
from app.services.groq_service import groq_service
from app.services.rag_service import rag_service

router = APIRouter()

VALID_CATEGORIES = {
    "bottle", "cable", "metal_nut", "screw",
    "tile", "toothbrush", "transistor", "zipper",
}

RAG_TOP_K = 5


def _build_rag_query(request: ChatRequest) -> str:
    """Compose a rich Qdrant search query from question + prediction context."""
    parts = [request.question, request.product_category]
    if request.prediction:
        pred = request.prediction
        parts.append(pred.status)
        if pred.severity:
            parts.append(pred.severity)
        if pred.defect_type:
            parts.append(pred.defect_type)
    return " ".join(parts)


@router.post("/chat/ask", response_model=ChatResponse)
async def ask_question(request: ChatRequest):
    """
    Answer a user question using RAG-retrieved SOP evidence and Groq LLM.

    Flow:
      1. Validate product category.
      2. Search Qdrant for relevant SOP/QA chunks.
      3. Send question + prediction context + evidence to Groq.
      4. Return structured answer with evidence references.

    All three services (Qdrant, Groq) are optional at the field level —
    the endpoint degrades gracefully if either is unavailable.
    """
    # 1. Validate category
    if request.product_category not in VALID_CATEGORIES:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Invalid product_category '{request.product_category}'. "
                f"Must be one of: {sorted(VALID_CATEGORIES)}"
            ),
        )

    warning: str | None = None
    rag_results: list[dict] = []
    evidence_items: list[EvidenceItem] = []

    # 2. RAG search (non-fatal — degrade gracefully)
    if rag_service.is_available():
        try:
            rag_query = _build_rag_query(request)
            rag_results = rag_service.search(query=rag_query, top_k=RAG_TOP_K)
            evidence_items = [EvidenceItem(**r) for r in rag_results]
        except Exception as exc:
            warning = f"Evidence search failed: {exc}. Answer is not grounded in SOP documents."
    else:
        warning = (
            "Qdrant is not reachable — RAG evidence unavailable. "
            "Start Qdrant with: docker compose up -d"
        )

    # 3. Groq explanation
    if not groq_service.is_configured():
        raise HTTPException(
            status_code=503,
            detail=(
                "GROQ_API_KEY is not configured. "
                "Add your Groq API key to backend/.env and restart."
            ),
        )

    prediction_dict = request.prediction.model_dump() if request.prediction else None

    try:
        result = groq_service.generate_explanation(
            question=request.question,
            prediction=prediction_dict,
            rag_evidence=rag_results,
            product_category=request.product_category,
        )
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    return ChatResponse(
        question=request.question,
        answer=result["answer"],
        possible_root_cause=result["possible_root_cause"],
        recommended_action=result["recommended_action"],
        human_review_required=result["human_review_required"],
        evidence=evidence_items,
        groq_model_used=settings.GROQ_MODEL,
        warning=warning,
    )
