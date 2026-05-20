from typing import Optional

from pydantic import BaseModel, Field


class ChatPrediction(BaseModel):
    """Prediction context passed alongside the user's question."""
    status: str = Field(..., description="'normal' or 'defective'")
    defect_type: Optional[str] = Field(None, description="Defect type label if known")
    anomaly_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    severity: Optional[str] = Field(None, description="Normal / Minor / Major / Critical / Human Review Required")


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, description="User's follow-up question")
    product_category: str = Field(..., description="One of the 8 MVTec AD categories")
    prediction: Optional[ChatPrediction] = Field(
        None,
        description="Prediction context — include when asking about a specific inspection result",
    )


class EvidenceItem(BaseModel):
    document_name: str
    page_number: int
    score: Optional[float] = None
    text: str


class ChatResponse(BaseModel):
    question: str
    answer: str
    possible_root_cause: str
    recommended_action: str
    human_review_required: bool
    evidence: list[EvidenceItem]
    groq_model_used: str
    warning: Optional[str] = None   # set when Qdrant/Groq unavailable
