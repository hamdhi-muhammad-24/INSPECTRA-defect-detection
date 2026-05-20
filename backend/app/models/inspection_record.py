from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, String, Text

from app.core.database import Base


class InspectionRecord(Base):
    __tablename__ = "inspection_records"

    inspection_id = Column(String, primary_key=True, index=True)
    product_category = Column(String, nullable=False, index=True)
    image_filename = Column(String, nullable=False)
    image_path = Column(String, nullable=True)
    image_quality_status = Column(String, nullable=True)
    status = Column(String, nullable=False)          # "normal" | "defective"
    anomaly_score = Column(Float, nullable=True)
    severity = Column(String, nullable=True)
    explanation = Column(Text, nullable=True)
    possible_root_cause = Column(Text, nullable=True)
    recommended_action = Column(Text, nullable=True)
    human_review_required = Column(Boolean, default=False)
    evidence_json = Column(Text, nullable=True)      # JSON-serialised list
    report_path = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
