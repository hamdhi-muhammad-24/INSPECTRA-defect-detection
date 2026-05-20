from __future__ import annotations

import uuid
from pathlib import Path
from typing import Optional

from app.core.config import settings

EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
VECTOR_DIM = 384
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100
UPSERT_BATCH = 100

# Module-level lazy singleton so the model loads once per worker process
_embed_model = None


def _get_embed_model():
    global _embed_model
    if _embed_model is None:
        from sentence_transformers import SentenceTransformer
        _embed_model = SentenceTransformer(EMBED_MODEL)
    return _embed_model


def _get_client():
    from qdrant_client import QdrantClient
    kwargs: dict = {"url": settings.QDRANT_URL}
    if settings.QDRANT_API_KEY:
        kwargs["api_key"] = settings.QDRANT_API_KEY
    return QdrantClient(**kwargs)


def _chunk_text(text: str) -> list[str]:
    chunks, start = [], 0
    while start < len(text):
        chunk = text[start : start + CHUNK_SIZE].strip()
        if chunk:
            chunks.append(chunk)
        start += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks


class RAGService:
    """Handles Qdrant-backed RAG: search and document ingestion."""

    # ── Availability check ──────────────────────────────────────────────────

    def is_available(self) -> bool:
        try:
            _get_client().get_collections()
            return True
        except Exception:
            return False

    # ── Search ──────────────────────────────────────────────────────────────

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """Embed *query* and return top-k matching chunks from Qdrant."""
        model = _get_embed_model()
        vector = model.encode(query).tolist()
        client = _get_client()
        hits = client.search(
            collection_name=settings.QDRANT_COLLECTION_NAME,
            query_vector=vector,
            limit=top_k,
            with_payload=True,
        )
        return [
            {
                "document_name": h.payload.get("document_name", ""),
                "page_number": h.payload.get("page_number", 0),
                "score": round(h.score, 4),
                "text": h.payload.get("text", ""),
            }
            for h in hits
        ]

    # ── Ingestion (called from API endpoint) ────────────────────────────────

    def ingest_documents(self) -> dict:
        """
        Read PDFs from settings.RAG_DOCS_PATH, chunk, embed, and upsert
        to Qdrant. Recreates the collection each time (idempotent).
        """
        import pypdf
        from qdrant_client.models import Distance, PointStruct, VectorParams

        rag_path = Path(settings.RAG_DOCS_PATH)
        if not rag_path.exists():
            raise FileNotFoundError(f"RAG docs folder not found: {rag_path}")

        pdf_files = sorted(rag_path.glob("*.pdf"))
        if not pdf_files:
            raise FileNotFoundError(f"No PDF files found in {rag_path}")

        model = _get_embed_model()
        client = _get_client()

        # Recreate collection
        existing = [c.name for c in client.get_collections().collections]
        if settings.QDRANT_COLLECTION_NAME in existing:
            client.delete_collection(settings.QDRANT_COLLECTION_NAME)
        client.create_collection(
            collection_name=settings.QDRANT_COLLECTION_NAME,
            vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE),
        )

        all_points: list[PointStruct] = []

        for pdf_path in pdf_files:
            doc_name = pdf_path.name
            reader = pypdf.PdfReader(str(pdf_path))
            for page_idx, page in enumerate(reader.pages, start=1):
                page_text = page.extract_text() or ""
                if not page_text.strip():
                    continue
                for chunk_idx, chunk in enumerate(_chunk_text(page_text)):
                    vector = model.encode(chunk).tolist()
                    all_points.append(
                        PointStruct(
                            id=str(uuid.uuid4()),
                            vector=vector,
                            payload={
                                "document_name": doc_name,
                                "page_number": page_idx,
                                "chunk_id": f"{doc_name}_p{page_idx}_c{chunk_idx}",
                                "text": chunk,
                                "source_path": str(pdf_path),
                            },
                        )
                    )

        for i in range(0, len(all_points), UPSERT_BATCH):
            client.upsert(
                collection_name=settings.QDRANT_COLLECTION_NAME,
                points=all_points[i : i + UPSERT_BATCH],
            )

        return {
            "documents_processed": len(pdf_files),
            "total_vectors": len(all_points),
            "collection": settings.QDRANT_COLLECTION_NAME,
        }


rag_service = RAGService()
