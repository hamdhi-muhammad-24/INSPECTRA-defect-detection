from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.inspection_record import InspectionRecord
from app.services.history_service import get_by_id


# ── Layout constants ──────────────────────────────────────────────────────────

_PAGE_W = 595      # A4 points
_PAGE_H = 842
_MARGIN = 50
_CONTENT_W = _PAGE_W - 2 * _MARGIN

_BRAND_COLOR   = (0.05, 0.27, 0.53)   # dark blue
_ACCENT_COLOR  = (0.0,  0.60, 0.80)   # cyan-ish
_WARN_COLOR    = (0.80, 0.20, 0.10)   # red
_OK_COLOR      = (0.10, 0.55, 0.20)   # green
_LIGHT_GRAY    = (0.92, 0.92, 0.92)
_TEXT_DARK     = (0.10, 0.10, 0.10)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _resolve_reports_dir() -> Path:
    p = Path(settings.REPORTS_DIR)
    if not p.is_absolute():
        p = Path.cwd() / p
    p.mkdir(parents=True, exist_ok=True)
    return p


def _status_color(status: str):
    return _OK_COLOR if status == "normal" else _WARN_COLOR


def _severity_color(severity: Optional[str]):
    if not severity:
        return _TEXT_DARK
    s = severity.lower()
    if s == "normal":
        return _OK_COLOR
    if s == "minor":
        return (0.80, 0.60, 0.00)
    if s == "major":
        return (0.85, 0.35, 0.00)
    return _WARN_COLOR   # critical / human review


# ── Core builder ──────────────────────────────────────────────────────────────

def generate_report(inspection_id: str, db: Session) -> str:
    """
    Build a PDF report for the given inspection and return its file path.

    Raises FileNotFoundError if the inspection does not exist.
    Raises RuntimeError if ReportLab is unavailable.
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        from reportlab.lib.units import cm
    except ImportError as exc:
        raise RuntimeError(f"ReportLab is required for report generation: {exc}")

    record: Optional[InspectionRecord] = get_by_id(inspection_id, db)
    if record is None:
        raise FileNotFoundError(f"Inspection '{inspection_id}' not found.")

    reports_dir = _resolve_reports_dir()
    pdf_path = reports_dir / f"{inspection_id}.pdf"

    c = canvas.Canvas(str(pdf_path), pagesize=A4)
    _draw_page(c, record)
    c.save()

    # Persist report path in DB
    record.report_path = str(pdf_path)
    db.commit()

    return str(pdf_path)


# ── Page drawing ──────────────────────────────────────────────────────────────

def _draw_page(c, record: InspectionRecord) -> None:
    y = _PAGE_H - _MARGIN

    # ── Header band ──────────────────────────────────────────────────────────
    c.setFillColorRGB(*_BRAND_COLOR)
    c.rect(_MARGIN, y - 48, _CONTENT_W, 56, fill=1, stroke=0)

    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 20)
    c.drawString(_MARGIN + 12, y - 24, "INSPECTRA Inspection Report")

    c.setFont("Helvetica", 9)
    c.drawRightString(_PAGE_W - _MARGIN - 12, y - 14, f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    c.drawRightString(_PAGE_W - _MARGIN - 12, y - 26, f"Report ID: {record.inspection_id}")

    y -= 68

    # ── Inspection summary table ──────────────────────────────────────────────
    y = _section_title(c, "Inspection Summary", y)
    rows = [
        ("Inspection ID",      record.inspection_id),
        ("Product Category",   record.product_category.replace("_", " ").title()),
        ("Image Filename",     record.image_filename or "—"),
        ("Image Quality",      record.image_quality_status or "—"),
        ("Inspection Date",    record.created_at.strftime("%Y-%m-%d %H:%M UTC") if record.created_at else "—"),
    ]
    y = _kv_table(c, rows, y)

    # ── Result summary ────────────────────────────────────────────────────────
    y = _section_title(c, "Analysis Result", y)

    status_label = (record.status or "unknown").upper()
    sev_label    = record.severity or "—"
    score_label  = f"{record.anomaly_score:.4f}" if record.anomaly_score is not None else "—"
    review_label = "Yes" if record.human_review_required else "No"

    result_rows = [
        ("Status",                 status_label),
        ("Anomaly Score",          score_label),
        ("Severity",               sev_label),
        ("Human Review Required",  review_label),
    ]

    # Draw with coloured status text
    y = _kv_table_with_colors(c, result_rows, y, {
        "Status":   _status_color(record.status or ""),
        "Severity": _severity_color(record.severity),
        "Human Review Required": _WARN_COLOR if record.human_review_required else _OK_COLOR,
    })

    # ── AI Explanation ────────────────────────────────────────────────────────
    if record.explanation:
        y = _section_title(c, "AI Explanation", y)
        y = _wrapped_text(c, record.explanation, y)

    # ── Root Cause ────────────────────────────────────────────────────────────
    if record.possible_root_cause:
        y = _section_title(c, "Possible Root Cause", y)
        y = _wrapped_text(c, record.possible_root_cause, y)

    # ── Recommended Action ────────────────────────────────────────────────────
    if record.recommended_action:
        y = _section_title(c, "Recommended Action", y)
        y = _wrapped_text(c, record.recommended_action, y)

    # ── SOP Evidence ──────────────────────────────────────────────────────────
    if record.evidence_json:
        try:
            evidence = json.loads(record.evidence_json) if isinstance(record.evidence_json, str) else record.evidence_json
        except (json.JSONDecodeError, TypeError):
            evidence = []
        if evidence:
            y = _section_title(c, f"SOP Evidence ({len(evidence)} source(s))", y)
            for i, chunk in enumerate(evidence[:5], 1):
                doc  = chunk.get("document_name", "Unknown")
                page = chunk.get("page_number", "—")
                text = chunk.get("text", "")
                score = chunk.get("score")
                header = f"{i}. {doc}  |  Page {page}"
                if score is not None:
                    header += f"  |  Relevance: {score:.3f}"
                y = _evidence_block(c, header, text, y)

    # ── Footer disclaimer ─────────────────────────────────────────────────────
    _draw_footer(c)


# ── Drawing primitives ────────────────────────────────────────────────────────

def _section_title(c, title: str, y: float) -> float:
    y -= 14
    c.setFillColorRGB(*_ACCENT_COLOR)
    c.rect(_MARGIN, y - 3, _CONTENT_W, 18, fill=1, stroke=0)
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(_MARGIN + 6, y + 1, title)
    return y - 10


def _kv_table(c, rows: list[tuple[str, str]], y: float) -> float:
    return _kv_table_with_colors(c, rows, y, {})


def _kv_table_with_colors(c, rows: list[tuple[str, str]], y: float, colors: dict) -> float:
    col1_w = 175
    row_h  = 18
    for i, (key, val) in enumerate(rows):
        bg = _LIGHT_GRAY if i % 2 == 0 else (1, 1, 1)
        c.setFillColorRGB(*bg)
        c.rect(_MARGIN, y - row_h + 4, _CONTENT_W, row_h, fill=1, stroke=0)

        c.setFillColorRGB(*_TEXT_DARK)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(_MARGIN + 6, y - 8, key)

        val_color = colors.get(key, _TEXT_DARK)
        c.setFillColorRGB(*val_color)
        c.setFont("Helvetica", 9)
        c.drawString(_MARGIN + col1_w, y - 8, str(val))

        y -= row_h
    return y - 4


def _wrapped_text(c, text: str, y: float, font_size: int = 9, line_height: int = 13) -> float:
    """Draw text wrapped to content width; add a new page if needed."""
    from reportlab.pdfbase.pdfmetrics import stringWidth

    max_w = _CONTENT_W - 12
    c.setFillColorRGB(*_TEXT_DARK)
    c.setFont("Helvetica", font_size)

    words = text.split()
    if not words:
        return y

    current = ""
    for word in words:
        candidate = (current + " " + word).strip()
        if stringWidth(candidate, "Helvetica", font_size) <= max_w:
            current = candidate
        else:
            if current:
                if y < _MARGIN + 40:
                    c.showPage()
                    y = _PAGE_H - _MARGIN
                    _draw_footer(c)
                    c.setFont("Helvetica", font_size)
                c.drawString(_MARGIN + 6, y, current)
                y -= line_height
            current = word

    if current:
        if y < _MARGIN + 40:
            c.showPage()
            y = _PAGE_H - _MARGIN
            _draw_footer(c)
            c.setFont("Helvetica", font_size)
        c.drawString(_MARGIN + 6, y, current)
        y -= line_height

    return y - 4


def _evidence_block(c, header: str, text: str, y: float) -> float:
    if y < _MARGIN + 80:
        c.showPage()
        y = _PAGE_H - _MARGIN
        _draw_footer(c)

    c.setFillColorRGB(*_LIGHT_GRAY)
    c.rect(_MARGIN, y - 10, _CONTENT_W, 14, fill=1, stroke=0)
    c.setFillColorRGB(*_BRAND_COLOR)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(_MARGIN + 6, y - 5, header)
    y -= 14

    y = _wrapped_text(c, text[:600] + ("…" if len(text) > 600 else ""), y, font_size=8, line_height=11)
    return y - 4


def _draw_footer(c) -> None:
    disclaimer = (
        "This report is AI-assisted and should be reviewed by qualified personnel for critical defects. "
        "INSPECTRA does not replace certified quality assurance processes."
    )
    c.setFillColorRGB(0.50, 0.50, 0.50)
    c.setFont("Helvetica-Oblique", 7)
    c.drawCentredString(_PAGE_W / 2, _MARGIN - 20, disclaimer)

    c.setStrokeColorRGB(0.75, 0.75, 0.75)
    c.line(_MARGIN, _MARGIN - 8, _PAGE_W - _MARGIN, _MARGIN - 8)
