from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from app.services.rag_service import rag_service

router = APIRouter()


# ── Request / response schemas ───────────────────────────────────────────────


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Search query")
    top_k: int = Field(5, ge=1, le=20, description="Number of results to return")


class SearchResult(BaseModel):
    document_name: str
    page_number: int
    score: float
    text: str


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]


class IngestResponse(BaseModel):
    status: str
    message: str


# ── Helpers ──────────────────────────────────────────────────────────────────


def _require_qdrant() -> None:
    if not rag_service.is_available():
        raise HTTPException(
            status_code=503,
            detail=(
                "Qdrant is not reachable. "
                "Start it with: docker compose up -d"
            ),
        )


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.post("/rag/ingest", response_model=IngestResponse)
async def ingest_documents(background_tasks: BackgroundTasks):
    """
    Trigger RAG document ingestion into Qdrant.

    Reads all PDFs from data/rag_documents/, chunks them, embeds each chunk
    with sentence-transformers/all-MiniLM-L6-v2, and upserts to Qdrant.
    The operation runs in the background — check backend logs for progress.
    Re-running is safe: the collection is recreated from scratch each time.
    """
    _require_qdrant()

    def _run() -> None:
        try:
            result = rag_service.ingest_documents()
            print(
                f"[RAG] Ingestion complete: "
                f"{result['documents_processed']} docs, "
                f"{result['total_vectors']} vectors"
            )
        except Exception as exc:
            print(f"[RAG] Ingestion failed: {exc}")

    background_tasks.add_task(_run)
    return IngestResponse(
        status="started",
        message=(
            "Ingestion started in background. "
            "Watch backend logs for progress. "
            "Then test with POST /api/rag/search."
        ),
    )


@router.post("/rag/search", response_model=SearchResponse)
async def search_documents(request: SearchRequest):
    """
    Search ingested RAG documents in Qdrant.

    Returns the top-k most relevant chunks for the given query,
    ranked by cosine similarity of their embeddings.
    """
    _require_qdrant()

    try:
        results = rag_service.search(query=request.query, top_k=request.top_k)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Search failed: {exc}")

    return SearchResponse(
        query=request.query,
        results=[SearchResult(**r) for r in results],
    )
