import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.database import init_db
from app.api import health, predict, rag, chat, reports, history


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="INSPECTRA Defect Detection API",
    description="AI-powered industrial defect detection and root-cause assistant.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api", tags=["Health"])
app.include_router(predict.router, prefix="/api", tags=["Predict"])
app.include_router(rag.router, prefix="/api", tags=["RAG"])
app.include_router(chat.router, prefix="/api", tags=["Chat"])
app.include_router(reports.router, prefix="/api", tags=["Reports"])
app.include_router(history.router, prefix="/api", tags=["History"])

_heatmap_dir = os.path.join(os.path.dirname(__file__), "..", "..", "reports", "heatmaps")
os.makedirs(_heatmap_dir, exist_ok=True)
app.mount("/heatmaps", StaticFiles(directory=_heatmap_dir), name="heatmaps")
