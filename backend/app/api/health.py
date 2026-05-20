from fastapi import APIRouter
from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse

from app.core.config import settings

router = APIRouter()


def _check_qdrant() -> bool:
    try:
        client = QdrantClient(url=settings.QDRANT_URL, timeout=2)
        client.get_collections()
        return True
    except Exception:
        return False


@router.get("/health")
async def health_check():
    qdrant_ok = _check_qdrant()
    return {
        "status": "ok",
        "service": "INSPECTRA backend",
        "qdrant_configured": qdrant_ok,
        "groq_configured": settings.groq_configured,
    }
