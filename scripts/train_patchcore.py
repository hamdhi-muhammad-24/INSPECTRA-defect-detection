#!/usr/bin/env python3
"""
Train a PatchCore anomaly detection model on one MVTec AD category.

Run from the backend/ directory:
    python ../scripts/train_patchcore.py --category bottle
    python ../scripts/train_patchcore.py --category bottle --image-size 256 --batch-size 1
    python ../scripts/train_patchcore.py --category bottle --device cpu

Dataset path expected (auto-detected from .env or default):
    data/mvtec_ad/<category>/<category>/train/good/

Trained artifacts saved to:
    models/trained/<category>/model.ckpt
    models/trained/<category>/metadata.json

Training order recommended for limited GPU memory (4 GB):
    bottle → metal_nut → transistor → tile → cable → screw → zipper → toothbrush
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

# ── Path setup ────────────────────────────────────────────────────────────────

_PROJECT_ROOT = Path(__file__).parent.parent
_ENV_PATH = _PROJECT_ROOT / "backend" / ".env"
if _ENV_PATH.exists():
    from dotenv import load_dotenv
    load_dotenv(_ENV_PATH)

DATASET_PATH = Path(os.getenv("DATASET_PATH", str(_PROJECT_ROOT / "data" / "mvtec_ad")))
if not DATASET_PATH.is_absolute():
    DATASET_PATH = (_PROJECT_ROOT / "backend" / DATASET_PATH).resolve()

MODEL_DIR = Path(os.getenv("MODEL_DIR", str(_PROJECT_ROOT / "models" / "trained")))
if not MODEL_DIR.is_absolute():
    MODEL_DIR = (_PROJECT_ROOT / "backend" / MODEL_DIR).resolve()

VALID_CATEGORIES = [
    "bottle", "cable", "metal_nut", "screw",
    "tile", "toothbrush", "transistor", "zipper",
]

# ── Argument parsing ──────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train PatchCore anomaly detection model on MVTec AD category."
    )
    parser.add_argument(
        "--category", required=True, choices=VALID_CATEGORIES,
        help="MVTec AD product category to train on.",
    )
    parser.add_argument(
        "--image-size", type=int, default=256,
        help="Image size (width = height). Default: 256. Use 224 if GPU OOM.",
    )
    parser.add_argument(
        "--batch-size", type=int, default=1,
        help="Training batch size. Default: 1 (recommended for 4 GB GPU).",
    )
    parser.add_argument(
        "--max-epochs", type=int, default=1,
        help="Max epochs. Default: 1 (PatchCore only needs one pass).",
    )
    parser.add_argument(
        "--device", choices=["auto", "gpu", "cpu"], default="auto",
        help="Device. 'auto' uses GPU if available, falls back to CPU.",
    )
    return parser.parse_args()


# ── Training logic ────────────────────────────────────────────────────────────

def _resolve_accelerator(device: str) -> str:
    try:
        import torch
        cuda_available = torch.cuda.is_available()
    except ImportError:
        cuda_available = False

    if device == "cpu":
        return "cpu"
    if device == "gpu":
        if not cuda_available:
            print("WARNING: --device gpu requested but CUDA not available. Falling back to CPU.")
            return "cpu"
        return "gpu"
    # auto
    return "gpu" if cuda_available else "cpu"


def _get_checkpoint_path(engine) -> Path | None:
    """Extract best checkpoint path from the Lightning trainer."""
    try:
        ckpt = engine.trainer.checkpoint_callback.best_model_path
        if ckpt and Path(ckpt).exists():
            return Path(ckpt)
    except AttributeError:
        pass
    # Fallback: look for last checkpoint in the log directory
    try:
        log_dir = Path(engine.trainer.log_dir)
        ckpts = sorted(log_dir.rglob("*.ckpt"))
        if ckpts:
            return ckpts[-1]
    except Exception:
        pass
    return None


def train(
    category: str,
    image_size: int,
    batch_size: int,
    max_epochs: int,
    accelerator: str,
) -> None:
    try:
        import anomalib
        from anomalib.data import MVTec
        from anomalib.engine import Engine
        from anomalib.models import Patchcore
    except ImportError as exc:
        print(f"ERROR: Anomalib not installed — {exc}")
        print("Run: pip install anomalib")
        sys.exit(1)

    # The double-folder path: data/mvtec_ad/bottle  → Anomalib looks for bottle/bottle/train/good
    category_root = DATASET_PATH / category
    if not (category_root / category / "train" / "good").exists():
        print(f"ERROR: Dataset not found at {category_root / category / 'train' / 'good'}")
        print(f"Expected structure: {category_root}/{category}/train/good/")
        sys.exit(1)

    output_dir = MODEL_DIR / category
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"  INSPECTRA — PatchCore Training")
    print(f"  Category   : {category}")
    print(f"  Image size : {image_size}×{image_size}")
    print(f"  Batch size : {batch_size}")
    print(f"  Device     : {accelerator}")
    print(f"  Output     : {output_dir}")
    print(f"  Anomalib   : {anomalib.__version__}")
    print(f"{'='*60}\n")

    datamodule = MVTec(
        root=str(category_root),
        category=category,
        image_size=(image_size, image_size),
        train_batch_size=batch_size,
        eval_batch_size=batch_size,
        num_workers=0,          # 0 is required on Windows; prevents DataLoader deadlock
        seed=42,
    )

    model = Patchcore(
        backbone="wide_resnet50_2",
        layers=["layer2", "layer3"],
        pre_trained=True,
        coreset_sampling_ratio=0.1,
        num_neighbors=9,
    )

    engine = Engine(
        max_epochs=max_epochs,
        accelerator=accelerator,
        devices=1,
        default_root_dir=str(output_dir / "lightning_logs"),
        enable_progress_bar=True,
        enable_model_summary=False,
    )

    print("Starting training ...")
    engine.fit(model=model, datamodule=datamodule)
    print("Training complete.")

    # ── Save checkpoint ───────────────────────────────────────────────────────
    ckpt_src = _get_checkpoint_path(engine)
    if ckpt_src:
        dest = output_dir / "model.ckpt"
        shutil.copy(ckpt_src, dest)
        print(f"Checkpoint saved: {dest}")
    else:
        print("WARNING: Could not locate checkpoint file. Check lightning_logs/.")

    # ── Save metadata ─────────────────────────────────────────────────────────
    metadata = {
        "category": category,
        "image_size": image_size,
        "batch_size": batch_size,
        "training_date": datetime.now().isoformat(),
        "model_type": "patchcore",
        "backbone": "wide_resnet50_2",
        "layers": ["layer2", "layer3"],
        "dataset_path": str(category_root / category),
        "anomalib_version": anomalib.__version__,
        "accelerator_used": accelerator,
        "checkpoint": str(output_dir / "model.ckpt") if ckpt_src else None,
    }
    meta_path = output_dir / "metadata.json"
    meta_path.write_text(json.dumps(metadata, indent=2))
    print(f"Metadata saved: {meta_path}")

    print(f"\nDone. Model artifacts in: {output_dir}")
    print(f"\nNext steps:")
    print(f"  Evaluate : python ../scripts/evaluate_model.py --category {category}")
    print(f"  Predict  : POST /api/predict/analyze with product_category={category}")


# ── GPU OOM retry ─────────────────────────────────────────────────────────────

def train_with_oom_fallback(args: argparse.Namespace) -> None:
    accelerator = _resolve_accelerator(args.device)

    if accelerator == "gpu":
        try:
            train(
                category=args.category,
                image_size=args.image_size,
                batch_size=args.batch_size,
                max_epochs=args.max_epochs,
                accelerator="gpu",
            )
            return
        except Exception as exc:
            exc_str = str(exc).lower()
            if "out of memory" in exc_str or "cuda" in exc_str:
                print(f"\nGPU OOM detected: {exc}")
                print("Retrying on CPU (this will be slower) ...\n")

                try:
                    import torch
                    torch.cuda.empty_cache()
                except Exception:
                    pass

                train(
                    category=args.category,
                    image_size=args.image_size,
                    batch_size=args.batch_size,
                    max_epochs=args.max_epochs,
                    accelerator="cpu",
                )
            else:
                raise
    else:
        train(
            category=args.category,
            image_size=args.image_size,
            batch_size=args.batch_size,
            max_epochs=args.max_epochs,
            accelerator=accelerator,
        )


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    args = parse_args()
    train_with_oom_fallback(args)
