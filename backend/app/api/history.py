import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.history_schema import HistoryStats, InspectionDetail, InspectionSummary
from app.services.history_service import delete_by_id, get_all, get_by_id, get_stats

router = APIRouter()


def _to_summary(record) -> InspectionSummary:
    return InspectionSummary(
        inspection_id=record.inspection_id,
        product_category=record.product_category,
        image_filename=record.image_filename,
        image_quality_status=record.image_quality_status,
        status=record.status,
        anomaly_score=record.anomaly_score,
        severity=record.severity,
        human_review_required=record.human_review_required,
        created_at=record.created_at,
    )


def _to_detail(record) -> InspectionDetail:
    evidence = None
    if record.evidence_json:
        try:
            evidence = json.loads(record.evidence_json) if isinstance(record.evidence_json, str) else record.evidence_json
        except (json.JSONDecodeError, TypeError):
            evidence = []

    return InspectionDetail(
        inspection_id=record.inspection_id,
        product_category=record.product_category,
        image_filename=record.image_filename,
        image_path=record.image_path,
        image_quality_status=record.image_quality_status,
        status=record.status,
        anomaly_score=record.anomaly_score,
        severity=record.severity,
        explanation=record.explanation,
        possible_root_cause=record.possible_root_cause,
        recommended_action=record.recommended_action,
        human_review_required=record.human_review_required,
        evidence=evidence,
        report_path=record.report_path,
        created_at=record.created_at,
    )


@router.get("/history", response_model=list[InspectionSummary])
async def list_inspections(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """
    Return a paginated list of inspection records, most-recent first.
    """
    records = get_all(db, skip=skip, limit=limit)
    return [_to_summary(r) for r in records]


@router.get("/history/stats/summary", response_model=HistoryStats)
async def inspection_stats(db: Session = Depends(get_db)):
    """
    Return aggregate statistics across all inspection records.
    """
    return get_stats(db)


@router.get("/history/{inspection_id}", response_model=InspectionDetail)
async def get_inspection(inspection_id: str, db: Session = Depends(get_db)):
    """
    Return the full detail record for a single inspection.
    """
    record = get_by_id(inspection_id, db)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Inspection '{inspection_id}' not found.")
    return _to_detail(record)


@router.delete("/history/{inspection_id}")
async def delete_inspection(inspection_id: str, db: Session = Depends(get_db)):
    """
    Delete an inspection record by ID (DB record only — never touches dataset files).
    """
    deleted = delete_by_id(inspection_id, db)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Inspection '{inspection_id}' not found.")
    return {"deleted": True, "inspection_id": inspection_id}
