from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models.inspection_record import InspectionRecord


# ── ID generation ─────────────────────────────────────────────────────────────

def _generate_inspection_id(db: Session) -> str:
    """
    Generate a unique inspection ID in the format INSP-YYYYMMDD-XXXX.
    XXXX is a zero-padded counter that resets daily.
    """
    today = datetime.utcnow().strftime("%Y%m%d")
    prefix = f"INSP-{today}-"

    # Count records already created today to get next sequential number
    count = (
        db.query(InspectionRecord)
        .filter(InspectionRecord.inspection_id.like(f"{prefix}%"))
        .count()
    )
    return f"{prefix}{str(count + 1).zfill(4)}"


# ── Save ──────────────────────────────────────────────────────────────────────

def save_inspection(record_data: dict[str, Any], db: Session) -> str:
    """
    Persist an inspection result to SQLite and return the generated inspection_id.

    *record_data* should contain the fields matching InspectionRecord columns.
    Any extra keys are silently ignored.
    """
    inspection_id = _generate_inspection_id(db)

    # Serialise the evidence list to JSON if provided as a Python list
    evidence = record_data.get("evidence_json")
    if isinstance(evidence, list):
        evidence = json.dumps(evidence)

    record = InspectionRecord(
        inspection_id=inspection_id,
        product_category=record_data.get("product_category", ""),
        image_filename=record_data.get("image_filename", ""),
        image_path=record_data.get("image_path"),
        image_quality_status=record_data.get("image_quality_status"),
        status=record_data.get("status", "unknown"),
        anomaly_score=record_data.get("anomaly_score"),
        severity=record_data.get("severity"),
        explanation=record_data.get("explanation"),
        possible_root_cause=record_data.get("possible_root_cause"),
        recommended_action=record_data.get("recommended_action"),
        human_review_required=bool(record_data.get("human_review_required", False)),
        evidence_json=evidence,
        report_path=record_data.get("report_path"),
        created_at=datetime.utcnow(),
    )

    db.add(record)
    db.commit()
    db.refresh(record)
    return inspection_id


# ── Read helpers (Phase 10 extends these) ─────────────────────────────────────

def get_all(db: Session, skip: int = 0, limit: int = 50) -> list[InspectionRecord]:
    return (
        db.query(InspectionRecord)
        .order_by(InspectionRecord.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_by_id(inspection_id: str, db: Session) -> InspectionRecord | None:
    return (
        db.query(InspectionRecord)
        .filter(InspectionRecord.inspection_id == inspection_id)
        .first()
    )


def delete_by_id(inspection_id: str, db: Session) -> bool:
    record = get_by_id(inspection_id, db)
    if not record:
        return False
    db.delete(record)
    db.commit()
    return True


def get_stats(db: Session) -> dict:
    """Return high-level inspection statistics."""
    from sqlalchemy import func

    total = db.query(func.count(InspectionRecord.inspection_id)).scalar() or 0
    normal = (
        db.query(func.count(InspectionRecord.inspection_id))
        .filter(InspectionRecord.status == "normal")
        .scalar() or 0
    )
    defective = (
        db.query(func.count(InspectionRecord.inspection_id))
        .filter(InspectionRecord.status == "defective")
        .scalar() or 0
    )
    human_review = (
        db.query(func.count(InspectionRecord.inspection_id))
        .filter(InspectionRecord.human_review_required == True)  # noqa: E712
        .scalar() or 0
    )

    # By category
    cat_rows = (
        db.query(InspectionRecord.product_category, func.count(InspectionRecord.inspection_id))
        .group_by(InspectionRecord.product_category)
        .all()
    )
    by_category = {row[0]: row[1] for row in cat_rows}

    # By severity
    sev_rows = (
        db.query(InspectionRecord.severity, func.count(InspectionRecord.inspection_id))
        .filter(InspectionRecord.severity.isnot(None))
        .group_by(InspectionRecord.severity)
        .all()
    )
    by_severity = {row[0]: row[1] for row in sev_rows}

    return {
        "total": total,
        "normal_count": normal,
        "defective_count": defective,
        "human_review_count": human_review,
        "by_category": by_category,
        "by_severity": by_severity,
    }
