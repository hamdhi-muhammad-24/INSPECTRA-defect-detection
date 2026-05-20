#!/usr/bin/env python3
"""
Test Qdrant connection and report collection status.

Run from the backend/ directory:
    python ../scripts/test_qdrant_connection.py
"""
import os
import sys
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
    from qdrant_client import QdrantClient
except ImportError:
    print("ERROR: qdrant-client not installed. Run: pip install qdrant-client")
    sys.exit(1)

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
COLLECTION = os.getenv("QDRANT_COLLECTION_NAME", "inspectra_rag_documents")


def main() -> None:
    print(f"Connecting to Qdrant at {QDRANT_URL} ...")
    try:
        client = QdrantClient(url=QDRANT_URL, timeout=5)
        collections = client.get_collections().collections
    except Exception as exc:
        print(f"\nERROR: Could not connect to Qdrant.")
        print(f"  {exc}")
        print("\nFix: make sure Docker is running and Qdrant is up:")
        print("  docker compose up -d")
        sys.exit(1)

    print(f"  Connected successfully.")
    print(f"  Collections found: {len(collections)}")
    for col in collections:
        print(f"    - {col.name}")

    if any(c.name == COLLECTION for c in collections):
        info = client.get_collection(COLLECTION)
        print(f"\n  Collection '{COLLECTION}':")
        print(f"    vectors_count = {info.vectors_count}")
        print(f"    points_count  = {info.points_count}")
        if info.points_count == 0:
            print("\n  Collection exists but has no vectors.")
            print("  Run: python ../scripts/ingest_rag_documents.py")
        else:
            print("\n  RAG documents are ingested and ready.")
    else:
        print(f"\n  Collection '{COLLECTION}' does not exist yet.")
        print("  Run: python ../scripts/ingest_rag_documents.py")


if __name__ == "__main__":
    main()
