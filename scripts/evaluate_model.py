#!/usr/bin/env python3
"""
Evaluate a trained PatchCore model against the MVTec AD test set.

Run from the backend/ directory:
    python ../scripts/evaluate_model.py --category bottle
    python ../scripts/evaluate_model.py --category bottle --image-size 256 --threshold 0.5

Results saved to:
    evaluation/vision_tests/<category>_evaluation.json
"""
from __future__ import annotations

import argparse
import json
import os
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

EVAL_DIR = _PROJECT_ROOT / "evaluation" / "vision_tests"

VALID_CATEGORIES = [
    "bottle", "cable", "metal_nut", "screw",
    "tile", "toothbrush", "transistor", "zipper",
]

# ── Argument parsing ──────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate a trained PatchCore model on MVTec AD test set."
    )
    parser.add_argument(
        "--category", required=True, choices=VALID_CATEGORIES,
        help="MVTec AD product category to evaluate.",
    )
    parser.add_argument(
        "--image-size", type=int, default=256,
        help="Image size used during training. Default: 256.",
    )
    parser.add_argument(
        "--threshold", type=float, default=0.5,
        help="Anomaly score threshold for normal/defective classification (0–1). Default: 0.5.",
    )
    parser.add_argument(
        "--device", choices=["auto", "gpu", "cpu"], default="auto",
        help="Device. Default: auto.",
    )
    return parser.parse_args()


# ── Metric helpers ────────────────────────────────────────────────────────────

def _compute_metrics(
    y_true: list[int], y_pred: list[int]
) -> dict:
    """
    Compute binary classification metrics.
    Label convention: 0 = normal, 1 = defective.
    """
    tp = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 1)
    tn = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 0)
    fp = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 1)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 0)

    total = len(y_true)
    accuracy  = (tp + tn) / total if total else 0.0
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall    = tp / (tp + fn) if (tp + fn) else 0.0
    f1        = (
        2 * precision * recall / (precision + recall)
        if (precision + recall) else 0.0
    )

    return {
        "accuracy":  round(accuracy, 4),
        "precision": round(precision, 4),
        "recall":    round(recall, 4),
        "f1_score":  round(f1, 4),
        "confusion_matrix": {
            "true_positive":  tp,
            "true_negative":  tn,
            "false_positive": fp,
            "false_negative": fn,
        },
        "total_samples": total,
        "normal_samples":    tn + fp,
        "defective_samples": tp + fn,
    }


# ── Evaluation logic ──────────────────────────────────────────────────────────

def evaluate(
    category: str,
    image_size: int,
    threshold: float,
    device: str,
) -> None:
    try:
        import torch
        from anomalib.data import MVTec
        from anomalib.engine import Engine
        from anomalib.models import Patchcore
    except ImportError as exc:
        print(f"ERROR: Missing dependency — {exc}")
        print("Run: pip install anomalib torch torchvision")
        sys.exit(1)

    # ── Resolve checkpoint ────────────────────────────────────────────────────
    model_dir = MODEL_DIR / category
    checkpoint = model_dir / "model.ckpt"
    if not checkpoint.exists():
        print(f"ERROR: No trained model found at {checkpoint}")
        print(f"Train first: python ../scripts/train_patchcore.py --category {category}")
        sys.exit(1)

    # ── Resolve dataset ───────────────────────────────────────────────────────
    category_root = DATASET_PATH / category
    test_good = category_root / category / "test" / "good"
    if not test_good.exists():
        print(f"ERROR: Test dataset not found at {test_good}")
        sys.exit(1)

    # ── Resolve accelerator ───────────────────────────────────────────────────
    if device == "auto":
        accelerator = "gpu" if torch.cuda.is_available() else "cpu"
    elif device == "gpu":
        accelerator = "gpu" if torch.cuda.is_available() else "cpu"
    else:
        accelerator = "cpu"

    print(f"\n{'='*60}")
    print(f"  INSPECTRA — PatchCore Evaluation")
    print(f"  Category   : {category}")
    print(f"  Image size : {image_size}×{image_size}")
    print(f"  Threshold  : {threshold}")
    print(f"  Device     : {accelerator}")
    print(f"  Checkpoint : {checkpoint}")
    print(f"{'='*60}\n")

    # ── Load model from checkpoint ────────────────────────────────────────────
    print("Loading model from checkpoint ...")
    model = Patchcore.load_from_checkpoint(str(checkpoint))

    # ── Build test datamodule ─────────────────────────────────────────────────
    datamodule = MVTec(
        root=str(category_root),
        category=category,
        image_size=(image_size, image_size),
        train_batch_size=1,
        eval_batch_size=1,
        num_workers=0,
        seed=42,
    )

    engine = Engine(
        accelerator=accelerator,
        devices=1,
        enable_progress_bar=True,
        enable_model_summary=False,
    )

    # ── Run inference on test set ─────────────────────────────────────────────
    print("Running inference on test set ...")
    predictions = engine.predict(model=model, datamodule=datamodule)

    # ── Collect scores and ground-truth labels ────────────────────────────────
    y_true: list[int] = []   # 0 = normal, 1 = defective
    y_pred: list[int] = []
    scores: list[float] = []
    per_image: list[dict] = []

    for batch in predictions:
        batch_labels = batch.get("label", batch.get("gt_label", []))
        batch_scores = batch.get("pred_score", batch.get("anomaly_maps", []))
        batch_paths  = batch.get("image_path", [""] * len(batch_labels))

        # Normalise to lists
        if hasattr(batch_labels, "tolist"):
            batch_labels = batch_labels.tolist()
        if hasattr(batch_scores, "tolist"):
            batch_scores = batch_scores.tolist()
        if not isinstance(batch_scores, list):
            batch_scores = list(batch_scores)

        for label, score, path in zip(batch_labels, batch_scores, batch_paths):
            gt  = int(label)          # 0 = good, 1 = anomalous
            sc  = float(score) if not isinstance(score, list) else float(score[0])
            pred = 1 if sc >= threshold else 0
            y_true.append(gt)
            y_pred.append(pred)
            scores.append(sc)
            per_image.append({
                "image_path": str(path),
                "ground_truth": "defective" if gt == 1 else "normal",
                "predicted":    "defective" if pred == 1 else "normal",
                "anomaly_score": round(sc, 4),
                "correct": gt == pred,
            })

    # ── Compute metrics ───────────────────────────────────────────────────────
    metrics = _compute_metrics(y_true, y_pred)

    # Try to compute AUROC as well
    try:
        from sklearn.metrics import roc_auc_score
        if len(set(y_true)) > 1:
            auroc = round(float(roc_auc_score(y_true, scores)), 4)
        else:
            auroc = None
    except ImportError:
        auroc = None

    result = {
        "category": category,
        "evaluated_at": datetime.now().isoformat(),
        "model_checkpoint": str(checkpoint),
        "image_size": image_size,
        "threshold_used": threshold,
        "metrics": metrics,
        "auroc": auroc,
        "per_image_results": per_image,
    }

    # ── Save results ──────────────────────────────────────────────────────────
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    out_path = EVAL_DIR / f"{category}_evaluation.json"
    out_path.write_text(json.dumps(result, indent=2))

    # ── Print summary ─────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  Evaluation Results — {category}")
    print(f"{'='*60}")
    m = metrics
    print(f"  Total samples    : {m['total_samples']}")
    print(f"  Normal           : {m['normal_samples']}")
    print(f"  Defective        : {m['defective_samples']}")
    print(f"  Accuracy         : {m['accuracy']:.4f}")
    print(f"  Precision        : {m['precision']:.4f}")
    print(f"  Recall           : {m['recall']:.4f}")
    print(f"  F1 Score         : {m['f1_score']:.4f}")
    if auroc is not None:
        print(f"  AUROC            : {auroc:.4f}")
    cm = m["confusion_matrix"]
    print(f"  Confusion matrix :")
    print(f"    TP={cm['true_positive']}  FP={cm['false_positive']}")
    print(f"    FN={cm['false_negative']}  TN={cm['true_negative']}")
    print(f"\n  Results saved to : {out_path}")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    args = parse_args()
    evaluate(
        category=args.category,
        image_size=args.image_size,
        threshold=args.threshold,
        device=args.device,
    )
