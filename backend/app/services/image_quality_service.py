from __future__ import annotations

import io
from dataclasses import dataclass, field
from enum import Enum

import cv2
import numpy as np
from PIL import Image, UnidentifiedImageError


# ── Constants ─────────────────────────────────────────────────────────────────

class QualityStatus(str, Enum):
    PASS = "PASS"
    PASS_WITH_WARNING = "PASS_WITH_WARNING"
    RETAKE_IMAGE = "RETAKE_IMAGE"


# Blur (Laplacian variance): higher = sharper
BLUR_RETAKE_THRESHOLD = 15.0      # below this → unusable (very motion-blurred)
BLUR_WARNING_THRESHOLD = 40.0     # below this → warn but allow

# Brightness (grayscale mean, 0–255)
BRIGHTNESS_TOO_DARK_RETAKE = 20
BRIGHTNESS_TOO_DARK_WARN   = 45
BRIGHTNESS_TOO_BRIGHT_RETAKE = 245
BRIGHTNESS_TOO_BRIGHT_WARN   = 230

# Resolution (pixels)
MIN_DIMENSION = 32    # either width or height below this → RETAKE


# ── Result dataclass ──────────────────────────────────────────────────────────

@dataclass
class QualityResult:
    quality_status: QualityStatus
    blur_score: float
    brightness_score: float
    resolution: dict          # {"width": int, "height": int}
    warnings: list[str] = field(default_factory=list)
    message: str = ""

    def to_dict(self) -> dict:
        return {
            "quality_status": self.quality_status.value,
            "blur_score": round(self.blur_score, 2),
            "brightness_score": round(self.brightness_score, 2),
            "resolution": self.resolution,
            "warnings": self.warnings,
            "message": self.message,
        }


# ── Service ───────────────────────────────────────────────────────────────────

class ImageQualityService:
    """
    Evaluates the quality of an uploaded image before anomaly detection.

    Checks performed:
      1. Resolution — image must be at least 64×64 px.
      2. Blur       — Laplacian variance indicates sharpness.
      3. Brightness — grayscale mean detects under/over-exposed images.

    Status levels:
      PASS             — all checks passed; safe to proceed.
      PASS_WITH_WARNING — minor issues; analysis is allowed with caution.
      RETAKE_IMAGE     — image is too poor for reliable analysis.
    """

    def check_quality(self, image_bytes: bytes) -> QualityResult:
        """
        Run all quality checks on *image_bytes*.

        Returns a QualityResult describing status, scores, and any warnings.
        Raises ValueError if the bytes cannot be decoded as an image.
        """
        # ── Decode image ──────────────────────────────────────────────────────
        try:
            pil_img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        except (UnidentifiedImageError, Exception) as exc:
            raise ValueError(f"Cannot decode image: {exc}") from exc

        width, height = pil_img.size
        resolution = {"width": width, "height": height}

        # Convert to OpenCV grayscale array for metric computation
        gray = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2GRAY)

        warnings: list[str] = []
        # Start optimistic; each check can escalate the status
        status = QualityStatus.PASS

        def _escalate(new_status: QualityStatus) -> None:
            nonlocal status
            # RETAKE > WARNING > PASS
            if new_status == QualityStatus.RETAKE_IMAGE:
                status = QualityStatus.RETAKE_IMAGE
            elif new_status == QualityStatus.PASS_WITH_WARNING and status == QualityStatus.PASS:
                status = QualityStatus.PASS_WITH_WARNING

        # ── 1. Resolution ─────────────────────────────────────────────────────
        if width < MIN_DIMENSION or height < MIN_DIMENSION:
            warnings.append(
                f"Resolution {width}×{height} is too small (minimum {MIN_DIMENSION}×{MIN_DIMENSION}). "
                "Upload a higher-resolution image."
            )
            _escalate(QualityStatus.RETAKE_IMAGE)

        # ── 2. Blur (Laplacian variance) ──────────────────────────────────────
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        blur_score = float(laplacian.var())

        if blur_score < BLUR_RETAKE_THRESHOLD:
            warnings.append(
                f"Image is too blurry (blur score {blur_score:.1f} < {BLUR_RETAKE_THRESHOLD}). "
                "Please retake with a stable camera and good focus."
            )
            _escalate(QualityStatus.RETAKE_IMAGE)
        elif blur_score < BLUR_WARNING_THRESHOLD:
            warnings.append(
                f"Image is slightly blurry (blur score {blur_score:.1f}). "
                "Results may be less accurate."
            )
            _escalate(QualityStatus.PASS_WITH_WARNING)

        # ── 3. Brightness ─────────────────────────────────────────────────────
        brightness_score = float(np.mean(gray))

        if brightness_score < BRIGHTNESS_TOO_DARK_RETAKE:
            warnings.append(
                f"Image is extremely dark (brightness {brightness_score:.1f}). "
                "Increase lighting and retake."
            )
            _escalate(QualityStatus.RETAKE_IMAGE)
        elif brightness_score < BRIGHTNESS_TOO_DARK_WARN:
            warnings.append(
                f"Image is underexposed (brightness {brightness_score:.1f}). "
                "Consider improving lighting."
            )
            _escalate(QualityStatus.PASS_WITH_WARNING)
        elif brightness_score > BRIGHTNESS_TOO_BRIGHT_RETAKE:
            warnings.append(
                f"Image is severely overexposed (brightness {brightness_score:.1f}). "
                "Reduce lighting or exposure and retake."
            )
            _escalate(QualityStatus.RETAKE_IMAGE)
        elif brightness_score > BRIGHTNESS_TOO_BRIGHT_WARN:
            warnings.append(
                f"Image is slightly overexposed (brightness {brightness_score:.1f}). "
                "Results may be less accurate."
            )
            _escalate(QualityStatus.PASS_WITH_WARNING)

        # ── Message ───────────────────────────────────────────────────────────
        message = _status_message(status)

        return QualityResult(
            quality_status=status,
            blur_score=blur_score,
            brightness_score=brightness_score,
            resolution=resolution,
            warnings=warnings,
            message=message,
        )


def _status_message(status: QualityStatus) -> str:
    return {
        QualityStatus.PASS: "Image quality is acceptable. Proceeding with analysis.",
        QualityStatus.PASS_WITH_WARNING: (
            "Image quality has minor issues. "
            "Analysis will proceed but results may be less reliable."
        ),
        QualityStatus.RETAKE_IMAGE: (
            "Image quality is insufficient for reliable analysis. "
            "Please retake the image and try again."
        ),
    }[status]


# Module-level singleton
image_quality_service = ImageQualityService()
