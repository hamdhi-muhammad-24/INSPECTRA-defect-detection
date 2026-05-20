from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.services.report_service import generate_report

router = APIRouter()


def _resolve_reports_dir() -> Path:
    p = Path(settings.REPORTS_DIR)
    if not p.is_absolute():
        p = Path.cwd() / p
    return p


@router.post("/reports/generate/{inspection_id}")
async def generate_inspection_report(inspection_id: str, db: Session = Depends(get_db)):
    """
    Generate a PDF report for an existing inspection record.

    Returns the download URL on success.
    """
    try:
        pdf_path = generate_report(inspection_id, db)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Report generation failed: {exc}")

    filename = Path(pdf_path).name
    return {
        "inspection_id": inspection_id,
        "report_filename": filename,
        "report_url": f"/api/reports/download/{filename}",
        "message": "Report generated successfully.",
    }


@router.get("/reports/download/{report_filename}")
async def download_report(report_filename: str):
    """
    Stream a generated PDF report as a file download.

    *report_filename* must end with .pdf and must already exist on disk.
    """
    if not report_filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only .pdf files may be downloaded.")

    # Guard against path traversal
    if "/" in report_filename or "\\" in report_filename or ".." in report_filename:
        raise HTTPException(status_code=400, detail="Invalid filename.")

    pdf_path = _resolve_reports_dir() / report_filename
    if not pdf_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Report '{report_filename}' not found. Generate it first via POST /api/reports/generate/<inspection_id>.",
        )

    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename=report_filename,
    )


@router.get("/reports/list")
async def list_reports(db: Session = Depends(get_db)):
    """
    Return a list of all generated report filenames found on disk.
    """
    reports_dir = _resolve_reports_dir()
    if not reports_dir.exists():
        return {"reports": [], "count": 0}

    files = sorted(reports_dir.glob("*.pdf"), key=lambda f: f.stat().st_mtime, reverse=True)
    return {
        "reports": [
            {
                "filename": f.name,
                "inspection_id": f.stem,
                "download_url": f"/api/reports/download/{f.name}",
                "size_kb": round(f.stat().st_size / 1024, 1),
            }
            for f in files
        ],
        "count": len(files),
    }
