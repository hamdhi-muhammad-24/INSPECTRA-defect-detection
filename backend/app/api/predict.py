from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.prediction_schema import ImageQualityResult, PredictionResponse, QualityOnlyResponse
from app.services.anomaly_service import anomaly_service
from app.services.groq_service import groq_service
from app.services.history_service import save_inspection
from app.services.image_quality_service import image_quality_service
from app.services.rag_service import rag_service
from app.services.severity_service import score_to_severity, severity_to_status

router = APIRouter()

VALID_CATEGORIES = {
    "bottle", "cable", "metal_nut", "screw",
    "tile", "toothbrush", "transistor", "zipper",
}

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/bmp", "image/tiff"}
MAX_FILE_SIZE_MB = 20

# Defect keywords appended to RAG queries to pull SOP-relevant chunks
_DEFECT_KEYWORDS = {
    "bottle":     "broken contamination crack surface defect",
    "cable":      "bent missing cut cable wire defect",
    "metal_nut":  "scratch bent flip thread defect",
    "screw":      "manipulated scratch thread defect",
    "tile":       "crack glue gray rough spot defect",
    "toothbrush": "defective bristle missing defect",
    "transistor": "bent lead damaged misplaced defect",
    "zipper":     "broken rough split defect",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _read_image_bytes(file: UploadFile) -> bytes:
    if file.content_type and file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=415,
            detail=(
                f"Unsupported file type '{file.content_type}'. "
                f"Allowed: JPEG, PNG, BMP, TIFF."
            ),
        )
    data = await file.read()
    if len(data) > MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum allowed size is {MAX_FILE_SIZE_MB} MB.",
        )
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    return data


def _validate_category(product_category: str) -> None:
    if product_category not in VALID_CATEGORIES:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Invalid product_category '{product_category}'. "
                f"Must be one of: {sorted(VALID_CATEGORIES)}"
            ),
        )


def _compose_rag_query(
    category: str,
    status: str,
    severity: str,
    user_question: Optional[str],
) -> str:
    """
    Build a rich Qdrant search query combining category, anomaly context,
    product-specific defect keywords, and any user question.
    """
    parts = [category, status, severity, "defect inspection SOP quality action"]
    parts.append(_DEFECT_KEYWORDS.get(category, "defect"))
    if user_question:
        parts.append(user_question)
    return " ".join(parts)


def _build_full_message(
    status: str,
    severity_label: str,
    score: float,
    warnings: list[str],
) -> str:
    if status == "normal":
        base = "Product appears normal. No significant anomaly detected."
    else:
        base = (
            f"Anomaly detected — severity: {severity_label} "
            f"(score {score:.3f}). "
            "Review SOP evidence and take corrective action."
        )
    if warnings:
        base += " | Warnings: " + "; ".join(warnings)
    return base


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/predict/image-quality")
async def check_image_quality(image: UploadFile = File(...)):
    """
    Check the quality of an uploaded product image.

    Evaluates blur, brightness, and resolution. Returns one of:
      - PASS             — image is good; safe to submit for analysis.
      - PASS_WITH_WARNING — minor quality issues; analysis may proceed.
      - RETAKE_IMAGE     — image is too poor; please retake before analysing.
    """
    image_bytes = await _read_image_bytes(image)
    try:
        result = image_quality_service.check_quality(image_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return result.to_dict()


@router.post("/predict/analyze", response_model=PredictionResponse | QualityOnlyResponse)
async def analyze_image(
    image: UploadFile = File(...),
    product_category: str = Form(...),
    db: Session = Depends(get_db),
):
    """
    Run anomaly detection on an uploaded product image.

    Flow:
      1. Validate category.
      2. Check image quality — stop early if RETAKE_IMAGE.
      3. Load the trained PatchCore model for the category.
      4. Run inference → get anomaly score.
      5. Map score to severity.
      6. Save result to SQLite.
      7. Return structured JSON including inspection_id.

    If the model for the selected category has not been trained yet,
    a clear instructional message is returned (no crash).
    """
    _validate_category(product_category)
    image_bytes = await _read_image_bytes(image)
    filename = image.filename or "upload.jpg"

    # ── Step 1: Image quality check ───────────────────────────────────────────
    try:
        quality = image_quality_service.check_quality(image_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    quality_dict = quality.to_dict()

    # Early exit on unacceptable image quality
    if quality.quality_status.value == "RETAKE_IMAGE":
        inspection_id = save_inspection(
            {
                "product_category": product_category,
                "image_filename": filename,
                "image_quality_status": quality.quality_status.value,
                "status": "quality_rejected",
                "human_review_required": False,
            },
            db,
        )
        return QualityOnlyResponse(
            inspection_id=inspection_id,
            product_category=product_category,
            image_quality=ImageQualityResult(**quality_dict),
            message=(
                "Image quality is too poor for reliable analysis. "
                "Please retake the image and try again."
            ),
        )

    # ── Step 2: Anomaly detection ─────────────────────────────────────────────
    try:
        inference = anomaly_service.predict(image_bytes, product_category)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Inference failed: {exc}")

    # Model not trained yet
    if not inference.get("trained"):
        inspection_id = save_inspection(
            {
                "product_category": product_category,
                "image_filename": filename,
                "image_quality_status": quality.quality_status.value,
                "status": "model_not_trained",
                "human_review_required": True,
            },
            db,
        )
        return PredictionResponse(
            inspection_id=inspection_id,
            product_category=product_category,
            status="model_not_trained",
            anomaly_score=None,
            severity=None,
            human_review_required=True,
            image_quality=ImageQualityResult(**quality_dict),
            model_type=None,
            fallback_used=False,
            message=inference.get("message", "Model not trained."),
        )

    # ── Step 3: Severity mapping ──────────────────────────────────────────────
    anomaly_score: float = inference["anomaly_score"]
    fallback_used: bool = inference.get("fallback", False)

    severity, human_review = score_to_severity(anomaly_score)
    # Force human review if fallback was used (result is unreliable)
    if fallback_used:
        human_review = True

    status = severity_to_status(severity)

    # Build human-readable message
    if fallback_used:
        message = (
            "Model inference encountered an error. "
            "Result is unreliable — please escalate for manual review."
        )
    elif status == "normal":
        message = "Product appears normal. No significant anomaly detected."
    else:
        message = (
            f"Anomaly detected with {severity.value.lower()} severity "
            f"(score {anomaly_score:.3f}). "
            "Retrieve SOP evidence before taking corrective action."
        )

    # ── Step 4: Persist to SQLite ─────────────────────────────────────────────
    inspection_id = save_inspection(
        {
            "product_category": product_category,
            "image_filename": filename,
            "image_quality_status": quality.quality_status.value,
            "status": status,
            "anomaly_score": anomaly_score,
            "severity": severity.value,
            "human_review_required": human_review,
        },
        db,
    )

    return PredictionResponse(
        inspection_id=inspection_id,
        product_category=product_category,
        status=status,
        anomaly_score=anomaly_score,
        severity=severity.value,
        human_review_required=human_review,
        image_quality=ImageQualityResult(**quality_dict),
        model_type=inference.get("model_type"),
        fallback_used=fallback_used,
        message=message,
    )


@router.post("/predict/full-inspection", response_model=PredictionResponse | QualityOnlyResponse)
async def full_inspection(
    image: UploadFile = File(...),
    product_category: str = Form(...),
    user_question: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """
    Complete AI inspection pipeline in a single call.

    Flow:
      1. Validate category.
      2. Check image quality — stop early if RETAKE_IMAGE.
      3. Run PatchCore anomaly detection.
      4. Auto-compose RAG search query from category + severity + defect keywords.
      5. Search Qdrant for SOP/QA evidence (degrades gracefully if unavailable).
      6. Send prediction context + evidence to Groq for explanation (degrades gracefully).
      7. Persist full record to SQLite.
      8. Return complete JSON including inspection_id for report generation.

    Optional *user_question* is appended to the RAG query and passed to Groq
    as the question context (useful for follow-up questions at inspection time).
    """
    _validate_category(product_category)
    image_bytes = await _read_image_bytes(image)
    filename = image.filename or "upload.jpg"

    # ── 1. Image quality ──────────────────────────────────────────────────────
    try:
        quality = image_quality_service.check_quality(image_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    quality_dict = quality.to_dict()

    if quality.quality_status.value == "RETAKE_IMAGE":
        inspection_id = save_inspection(
            {
                "product_category": product_category,
                "image_filename": filename,
                "image_quality_status": quality.quality_status.value,
                "status": "quality_rejected",
                "human_review_required": False,
            },
            db,
        )
        return QualityOnlyResponse(
            inspection_id=inspection_id,
            product_category=product_category,
            image_quality=ImageQualityResult(**quality_dict),
            message=(
                "Image quality is too poor for reliable analysis. "
                "Please retake the image and try again."
            ),
        )

    # ── 2. Anomaly detection ──────────────────────────────────────────────────
    try:
        inference = anomaly_service.predict(image_bytes, product_category)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Inference failed: {exc}")

    demo_mode: bool = inference.get("demo_mode", False)

    # demo_mode: model not trained but statistical baseline produced a valid score
    # fallback: model exists but inference threw an error
    if not inference.get("trained") and not demo_mode:
        inspection_id = save_inspection(
            {
                "product_category": product_category,
                "image_filename": filename,
                "image_quality_status": quality.quality_status.value,
                "status": "model_not_trained",
                "human_review_required": True,
            },
            db,
        )
        return PredictionResponse(
            inspection_id=inspection_id,
            product_category=product_category,
            status="model_not_trained",
            anomaly_score=None,
            severity=None,
            human_review_required=True,
            image_quality=ImageQualityResult(**quality_dict),
            model_type=None,
            fallback_used=False,
            message=inference.get("message", "Model not trained."),
        )

    anomaly_score: float = inference["anomaly_score"]
    fallback_used: bool = inference.get("fallback", False)
    severity, human_review = score_to_severity(anomaly_score)
    if fallback_used:
        human_review = True
    status = severity_to_status(severity)

    # ── 3. RAG search ─────────────────────────────────────────────────────────
    rag_results: list[dict] = []
    warnings: list[str] = []

    rag_query = _compose_rag_query(
        product_category, status, severity.value, user_question
    )

    if rag_service.is_available():
        try:
            rag_results = rag_service.search(query=rag_query, top_k=5)
        except Exception as exc:
            warnings.append(f"RAG search failed: {exc}")
    else:
        warnings.append(
            "Qdrant not reachable — SOP evidence unavailable. "
            "Start it with: docker compose up -d"
        )

    # ── 4. Groq explanation ───────────────────────────────────────────────────
    explanation: Optional[str] = None
    possible_root_cause: Optional[str] = None
    recommended_action: Optional[str] = None

    if groq_service.is_configured():
        try:
            question = user_question or (
                f"What is the possible root cause and recommended corrective action "
                f"for a {severity.value.lower()} anomaly detected on a {product_category}?"
            )
            prediction_ctx = {
                "status": status,
                "anomaly_score": anomaly_score,
                "severity": severity.value,
                "defect_type": "unknown_anomaly",
            }
            groq_result = groq_service.generate_explanation(
                question=question,
                prediction=prediction_ctx,
                rag_evidence=rag_results,
                product_category=product_category,
            )
            explanation = groq_result["answer"]
            possible_root_cause = groq_result["possible_root_cause"]
            recommended_action = groq_result["recommended_action"]
            # Escalate human_review if Groq says so
            if groq_result["human_review_required"]:
                human_review = True
        except Exception as exc:
            warnings.append(f"Groq explanation failed: {exc}")
            human_review = True     # force review when LLM is unavailable
    else:
        warnings.append(
            "GROQ_API_KEY not configured — AI explanation unavailable. "
            "Add your key to backend/.env."
        )
        human_review = True

    # Demo mode adds a warning note to the explanation
    if demo_mode:
        warnings.append(
            "Statistical baseline mode — train a PatchCore model for production accuracy."
        )

    # ── 5. Persist full record ────────────────────────────────────────────────
    inspection_id = save_inspection(
        {
            "product_category": product_category,
            "image_filename": filename,
            "image_quality_status": quality.quality_status.value,
            "status": status,
            "anomaly_score": anomaly_score,
            "severity": severity.value,
            "explanation": explanation,
            "possible_root_cause": possible_root_cause,
            "recommended_action": recommended_action,
            "human_review_required": human_review,
            "evidence_json": rag_results,   # serialised to JSON by save_inspection
        },
        db,
    )

    # ── 6. Return ─────────────────────────────────────────────────────────────
    return PredictionResponse(
        inspection_id=inspection_id,
        product_category=product_category,
        status=status,
        anomaly_score=anomaly_score,
        severity=severity.value,
        human_review_required=human_review,
        image_quality=ImageQualityResult(**quality_dict),
        model_type=inference.get("model_type"),
        fallback_used=fallback_used,
        demo_mode=demo_mode,
        message=_build_full_message(status, severity.value, anomaly_score, warnings),
        explanation=explanation,
        possible_root_cause=possible_root_cause,
        recommended_action=recommended_action,
        evidence=rag_results,
        report_available=False,
    )
