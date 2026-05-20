from __future__ import annotations

import io
import json
import math
from pathlib import Path
from typing import Any

from app.core.config import settings

VALID_CATEGORIES = {
    "bottle", "cable", "metal_nut", "screw",
    "tile", "toothbrush", "transistor", "zipper",
}

# Module-level model cache: category → loaded model
# Avoids reloading the same model on every request
_model_cache: dict[str, Any] = {}


# ── Path resolution ───────────────────────────────────────────────────────────

def _model_dir(category: str) -> Path:
    """Resolve the model directory, supporting both absolute and relative paths."""
    p = Path(settings.MODEL_DIR)
    if not p.is_absolute():
        # settings.MODEL_DIR is relative to backend/ (CWD at runtime)
        p = Path.cwd() / p
    return (p / category).resolve()


# ── Model loading ─────────────────────────────────────────────────────────────

def _load_anomalib_model(checkpoint: Path) -> Any:
    """Load a PatchCore model from a Lightning checkpoint."""
    from anomalib.models import Patchcore
    model = Patchcore.load_from_checkpoint(str(checkpoint))
    model.eval()
    return model


def _get_model(category: str) -> Any:
    """Return a cached model, loading it from checkpoint on first access."""
    if category not in _model_cache:
        ckpt = _model_dir(category) / "model.ckpt"
        _model_cache[category] = _load_anomalib_model(ckpt)
    return _model_cache[category]


# ── Image preprocessing ───────────────────────────────────────────────────────

def _preprocess(image_bytes: bytes, image_size: int):
    """Convert raw image bytes to a normalised (1, 3, H, W) tensor."""
    import torch
    from PIL import Image
    from torchvision import transforms

    pil = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    transform = transforms.Compose([
        transforms.Resize((image_size, image_size)),
        transforms.ToTensor(),
        transforms.Normalize(
            mean=[0.485, 0.456, 0.406],
            std=[0.229, 0.224, 0.225],
        ),
    ])
    return transform(pil).unsqueeze(0)   # (1, 3, H, W)


# ── Score extraction ──────────────────────────────────────────────────────────

def _extract_score(output: Any) -> float:
    """
    Pull a scalar anomaly score from whatever the model returned.
    Anomalib 1.x returns a dict; older versions may return a tensor directly.
    """
    import torch

    if isinstance(output, dict):
        raw = output.get("pred_score", output.get("anomaly_map"))
    else:
        raw = output

    if raw is None:
        return 0.5   # safe fallback

    if isinstance(raw, torch.Tensor):
        val = raw.squeeze()
        if val.dim() > 0:
            # anomaly_map returned instead of scalar — take max
            val = val.max()
        return float(val.item())

    return float(raw)


def _normalise_score(raw: float) -> float:
    """
    Clamp or sigmoid-normalise a raw score into [0, 1].
    PatchCore scores after MinMaxNorm are already in [0, 1];
    raw distance scores (before normalisation) can be >> 1.
    """
    if 0.0 <= raw <= 1.0:
        return round(raw, 4)
    # Apply sigmoid so any finite float maps into (0, 1)
    return round(1.0 / (1.0 + math.exp(-raw)), 4)


# ── Statistical demo mode ─────────────────────────────────────────────────────

def _statistical_demo(image_bytes: bytes, category: str) -> dict:
    """
    Fast anomaly scoring without a trained PatchCore model.

    Loads up to 20 'good' reference images from the MVTec dataset for the
    requested category, computes a per-pixel mean ± std map, then measures
    how much the uploaded image deviates from that reference distribution.
    The 90th-percentile normalised deviation is sigmoid-squashed into [0, 1].

    Falls back to a texture-based score when no reference images exist.
    """
    import cv2
    import numpy as np
    from pathlib import Path

    IMG_SIZE = 256

    def _decode(raw: bytes) -> np.ndarray:
        arr = np.frombuffer(raw, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Cannot decode image bytes")
        return cv2.resize(img, (IMG_SIZE, IMG_SIZE)).astype(np.float32)

    def _load_references(cat: str):
        base = Path.cwd()
        # Support both running from backend/ and from project root
        for candidate in [
            base / ".." / "data" / "mvtec_ad" / cat / cat / "train" / "good",
            base / "data" / "mvtec_ad" / cat / cat / "train" / "good",
        ]:
            candidate = candidate.resolve()
            if candidate.exists():
                refs = []
                for ext in ("*.png", "*.jpg", "*.jpeg", "*.bmp"):
                    refs.extend(candidate.glob(ext))
                return refs[:20]
        return []

    def _texture_score(img_gray: np.ndarray) -> float:
        """Fallback: edge density + local variance as proxy for anomaly."""
        edges = cv2.Canny(img_gray.astype(np.uint8), 50, 150).astype(np.float32) / 255.0
        edge_density = float(edges.mean())
        kernel = np.ones((8, 8), np.float32) / 64
        local_mean = cv2.filter2D(img_gray / 255.0, -1, kernel)
        local_sq_mean = cv2.filter2D((img_gray / 255.0) ** 2, -1, kernel)
        local_var = np.clip(local_sq_mean - local_mean ** 2, 0, None)
        var_score = float(local_var.mean()) * 10.0
        raw = (edge_density * 0.5 + var_score * 0.5)
        return float(1 / (1 + math.exp(-(raw * 6 - 3))))

    try:
        target = _decode(image_bytes)
        ref_paths = _load_references(category)

        if not ref_paths:
            gray = cv2.cvtColor(target.astype(np.uint8), cv2.COLOR_BGR2GRAY).astype(np.float32)
            score = _texture_score(gray)
            return {
                "trained": False,
                "anomaly_score": round(score, 4),
                "fallback": False,
                "demo_mode": True,
                "message": "Statistical baseline (no reference data). Train a model for production accuracy.",
                "image_size_used": IMG_SIZE,
                "model_type": "statistical_baseline",
            }

        # Build per-channel mean and std from reference good images
        ref_stack = []
        for p in ref_paths:
            r = cv2.imread(str(p))
            if r is not None:
                ref_stack.append(cv2.resize(r, (IMG_SIZE, IMG_SIZE)).astype(np.float32))

        if not ref_stack:
            gray = cv2.cvtColor(target.astype(np.uint8), cv2.COLOR_BGR2GRAY).astype(np.float32)
            score = _texture_score(gray)
        else:
            ref_arr = np.stack(ref_stack, axis=0)          # (N, H, W, 3)
            ref_mean = ref_arr.mean(axis=0)                 # (H, W, 3)
            ref_std  = ref_arr.std(axis=0) + 1e-6           # (H, W, 3)

            # Normalised absolute deviation per pixel-channel
            deviation = np.abs(target - ref_mean) / ref_std  # (H, W, 3)
            dev_map   = deviation.mean(axis=2)               # (H, W)

            # Score = 90th percentile of per-pixel deviation, sigmoid-squashed
            p90  = float(np.percentile(dev_map, 90))
            score = float(1 / (1 + math.exp(-(p90 - 2.5))))

        return {
            "trained": False,
            "anomaly_score": round(score, 4),
            "fallback": False,
            "demo_mode": True,
            "message": (
                f"Statistical baseline using {len(ref_stack)} reference images. "
                "Train a PatchCore model for production-grade accuracy."
            ),
            "image_size_used": IMG_SIZE,
            "model_type": "statistical_baseline",
        }

    except Exception as exc:
        print(f"[AnomalyService] Statistical demo error: {exc}")
        return {
            "trained": False,
            "anomaly_score": 0.5,
            "fallback": True,
            "demo_mode": True,
            "message": f"Demo mode error: {exc}",
            "image_size_used": IMG_SIZE,
            "model_type": "statistical_baseline",
        }


# ── Public service interface ──────────────────────────────────────────────────

class AnomalyService:
    """
    Loads trained PatchCore models and runs per-image anomaly inference.

    Models are cached in memory after the first load per category so repeated
    requests do not pay the checkpoint-loading cost.
    """

    def is_trained(self, category: str) -> bool:
        ckpt = _model_dir(category) / "model.ckpt"
        return ckpt.exists()

    def load_metadata(self, category: str) -> dict:
        meta_path = _model_dir(category) / "metadata.json"
        if meta_path.exists():
            return json.loads(meta_path.read_text())
        return {"image_size": 256, "model_type": "patchcore"}

    def invalidate_cache(self, category: str) -> None:
        """Remove a category from the model cache (e.g., after re-training)."""
        _model_cache.pop(category, None)

    def predict(self, image_bytes: bytes, category: str) -> dict:
        """
        Run anomaly detection on *image_bytes* for *category*.

        Returns a dict with:
            trained          — bool, False if no checkpoint exists
            anomaly_score    — float in [0, 1]
            fallback         — bool, True if Anomalib inference failed
            message          — human-readable status string
            image_size_used  — int
            model_type       — str
        """
        if category not in VALID_CATEGORIES:
            raise ValueError(
                f"Invalid category '{category}'. "
                f"Must be one of: {sorted(VALID_CATEGORIES)}"
            )

        # ── Not trained → statistical demo mode ──────────────────────────────
        if not self.is_trained(category):
            return _statistical_demo(image_bytes, category)

        metadata = self.load_metadata(category)
        image_size = int(metadata.get("image_size", 256))
        model_type = metadata.get("model_type", "patchcore")

        # ── Anomalib inference ────────────────────────────────────────────────
        try:
            import torch
            model = _get_model(category)

            # Move tensor to same device as model
            try:
                device = next(model.parameters()).device
            except StopIteration:
                device = torch.device("cpu")

            tensor = _preprocess(image_bytes, image_size).to(device)

            with torch.no_grad():
                output = model(tensor)

            raw_score = _extract_score(output)
            normalised = _normalise_score(raw_score)

            return {
                "trained": True,
                "anomaly_score": normalised,
                "fallback": False,
                "message": "Inference successful.",
                "image_size_used": image_size,
                "model_type": model_type,
            }

        except ImportError as exc:
            return _fallback_result(
                image_size, model_type,
                f"Anomalib/PyTorch not installed: {exc}",
            )
        except Exception as exc:
            # Evict bad model from cache so next request retries the load
            _model_cache.pop(category, None)
            return _fallback_result(
                image_size, model_type,
                f"Inference error: {exc}",
            )


def _fallback_result(image_size: int, model_type: str, reason: str) -> dict:
    """
    Return a safe fallback result when Anomalib inference fails.
    The score of 0.0 will map to 'Normal' via severity_service, so the caller
    (predict.py) should inspect the 'fallback' flag and add a warning.
    """
    print(f"[AnomalyService] FALLBACK: {reason}")
    return {
        "trained": True,
        "anomaly_score": 0.0,
        "fallback": True,
        "fallback_reason": reason,
        "message": (
            "Model inference encountered an error. "
            "Result is unreliable — human review required."
        ),
        "image_size_used": image_size,
        "model_type": model_type,
    }


anomaly_service = AnomalyService()
