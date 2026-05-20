from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class InspectionSummary(BaseModel):
    inspection_id: str
    product_category: str
    image_filename: str
    image_quality_status: Optional[str] = None
    status: str
    anomaly_score: Optional[float] = None
    severity: Optional[str] = None
    human_review_required: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class InspectionDetail(InspectionSummary):
    image_path: Optional[str] = None
    explanation: Optional[str] = None
    possible_root_cause: Optional[str] = None
    recommended_action: Optional[str] = None
    evidence: Optional[list[dict]] = None
    report_path: Optional[str] = None


class HistoryStats(BaseModel):
    total: int
    normal_count: int
    defective_count: int
    human_review_count: int
    by_category: dict[str, int]
    by_severity: dict[str, int]
