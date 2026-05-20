from typing import Optional

from pydantic import BaseModel, ConfigDict


class ImageQualityResult(BaseModel):
    quality_status: str
    blur_score: float
    brightness_score: float
    resolution: dict
    warnings: list[str]
    message: str


class PredictionResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    inspection_id: str
    product_category: str

    # Anomaly result
    status: str                       # "normal" | "defective"
    anomaly_score: Optional[float]    # 0.0 – 1.0
    severity: Optional[str]           # Severity label
    human_review_required: bool

    # Quality gate
    image_quality: ImageQualityResult

    # Model metadata
    model_type: Optional[str] = None
    fallback_used: bool = False
    demo_mode: bool = False

    # Contextual message
    message: str

    # Full-inspection fields (RAG + Groq)
    explanation: Optional[str] = None
    possible_root_cause: Optional[str] = None
    recommended_action: Optional[str] = None
    evidence: Optional[list[dict]] = None
    report_available: bool = False


class QualityOnlyResponse(BaseModel):
    """Returned when image quality fails and analysis is skipped."""
    inspection_id: str
    product_category: str
    status: str = "quality_rejected"
    image_quality: ImageQualityResult
    message: str
    human_review_required: bool = False
