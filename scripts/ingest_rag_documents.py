#!/usr/bin/env python3
"""
Ingest RAG PDF documents into Qdrant.

Run from the backend/ directory:
    python ../scripts/ingest_rag_documents.py

This script is idempotent: it deletes and recreates the Qdrant collection
on every run so re-running never creates duplicate vectors.
"""
import os
import sys
import uuid
from pathlib import Path

# Load backend/.env regardless of CWD
_env_path = Path(__file__).parent.parent / "backend" / ".env"
if _env_path.exists():
    from dotenv import load_dotenv
    load_dotenv(_env_path)
else:
    print(f"WARNING: .env not found at {_env_path}")
    print("         Copy backend/.env.example to backend/.env and fill in your values.")

try:
    import pypdf
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, PointStruct, VectorParams
    from sentence_transformers import SentenceTransformer
except ImportError as exc:
    print(f"ERROR: Missing dependency — {exc}")
    print("Run: pip install -r requirements.txt")
    sys.exit(1)

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")
COLLECTION = os.getenv("QDRANT_COLLECTION_NAME", "inspectra_rag_documents")
RAG_DOCS_PATH = Path(__file__).parent.parent / "data" / "rag_documents"

EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
VECTOR_DIM = 384        # output dim of all-MiniLM-L6-v2
CHUNK_SIZE = 800        # characters per chunk
CHUNK_OVERLAP = 100     # overlap between consecutive chunks
UPSERT_BATCH = 100      # Qdrant upsert batch size


# ── Text utilities ──────────────────────────────────────────────────────────


def extract_pages(pdf_path: Path) -> list[tuple[int, str]]:
    """Return list of (page_number, text) tuples from a PDF."""
    reader = pypdf.PdfReader(str(pdf_path))
    pages = []
    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if text.strip():
            pages.append((i, text))
    return pages


def chunk_text(text: str) -> list[str]:
    """Split text into overlapping chunks."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + CHUNK_SIZE
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks


# ── Main ────────────────────────────────────────────────────────────────────


def main() -> None:
    # 1. Verify PDF folder
    if not RAG_DOCS_PATH.exists():
        print(f"ERROR: RAG documents folder not found: {RAG_DOCS_PATH}")
        sys.exit(1)

    pdf_files = sorted(RAG_DOCS_PATH.glob("*.pdf"))
    if not pdf_files:
        print(f"ERROR: No PDF files found in {RAG_DOCS_PATH}")
        sys.exit(1)

    print(f"Found {len(pdf_files)} PDF(s) in {RAG_DOCS_PATH}")
    for f in pdf_files:
        print(f"  - {f.name}")

    # 2. Load embedding model
    print(f"\nLoading embedding model: {EMBED_MODEL}")
    print("  (first run downloads ~90 MB — subsequent runs use cache)")
    model = SentenceTransformer(EMBED_MODEL)
    print("  Model loaded.")

    # 3. Connect to Qdrant
    print(f"\nConnecting to Qdrant at {QDRANT_URL} ...")
    try:
        client_kwargs = {"url": QDRANT_URL}
        if QDRANT_API_KEY:
            client_kwargs["api_key"] = QDRANT_API_KEY
        client = QdrantClient(**client_kwargs)
        client.get_collections()  # connection test
    except Exception as exc:
        print(f"ERROR: Cannot connect to Qdrant — {exc}")
        print("Fix: docker compose up -d")
        sys.exit(1)
    print("  Connected.")

    # 4. Recreate collection (idempotent)
    existing = [c.name for c in client.get_collections().collections]
    if COLLECTION in existing:
        print(f"  Deleting existing collection '{COLLECTION}' ...")
        client.delete_collection(COLLECTION)

    client.create_collection(
        collection_name=COLLECTION,
        vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE),
    )
    print(f"  Created collection '{COLLECTION}' (dim={VECTOR_DIM}, metric=COSINE).")

    # 5. Chunk + embed + collect points
    all_points: list[PointStruct] = []
    total_chunks = 0

    for pdf_path in pdf_files:
        doc_name = pdf_path.name
        print(f"\nProcessing: {doc_name}")
        pages = extract_pages(pdf_path)

        if not pages:
            print("  WARNING: No text extracted — PDF may be scanned/image-only. Skipping.")
            continue

        doc_chunks = 0
        for page_num, page_text in pages:
            for chunk_idx, chunk in enumerate(chunk_text(page_text)):
                vector = model.encode(chunk).tolist()
                all_points.append(
                    PointStruct(
                        id=str(uuid.uuid4()),
                        vector=vector,
                        payload={
                            "document_name": doc_name,
                            "page_number": page_num,
                            "chunk_id": f"{doc_name}_p{page_num}_c{chunk_idx}",
                            "text": chunk,
                            "source_path": str(pdf_path),
                        },
                    )
                )
                doc_chunks += 1
                total_chunks += 1

        print(f"  {len(pages)} page(s) → {doc_chunks} chunk(s)")

    # 6. Upsert in batches
    print(f"\nUpserting {total_chunks} vectors to Qdrant ...")
    for i in range(0, len(all_points), UPSERT_BATCH):
        batch = all_points[i : i + UPSERT_BATCH]
        client.upsert(collection_name=COLLECTION, points=batch)
        done = min(i + UPSERT_BATCH, total_chunks)
        print(f"  [{done}/{total_chunks}] vectors upserted")

    print(f"\nIngestion complete.")
    print(f"  Collection : {COLLECTION}")
    print(f"  Total vectors: {total_chunks}")
    print(f"\nVerify with: python ../scripts/test_qdrant_connection.py")


if __name__ == "__main__":
    main()
