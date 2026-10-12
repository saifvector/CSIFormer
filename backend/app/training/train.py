"""
CSIFormer Training Engine.

Features:
- Optimized for NVIDIA GeForce RTX 3050 Laptop GPU (4 GB VRAM)
- Automatic Mixed Precision (torch.cuda.amp with GradScaler)
- Multi-Task Loss: CrossEntropy (Activity) + BCE (Presence) + BCE (Motion)
- AdamW Optimizer with Cosine Annealing Learning Rate Schedule
- Gradient Clipping (norm=1.0)
- Early Stopping with validation loss monitoring
- Robust Checkpoint Saving & Resumption (best_csiformer.pth & latest_checkpoint.pth)
- TensorBoard Metrics Logging
- Full Training Report Generation (reports/training_report.md)
"""

import os
import sys
import time
import json
import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List, Union
import numpy as np
import torch
import torch.nn as nn
from torch.utils.tensorboard import SummaryWriter

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
sys.path.append(str(BASE_DIR / "backend"))

from app.models.csiformernet import CSIFormerNet
from app.datasets.combined_dataset import create_dataloaders, CombinedCSIDataset
from app.evaluation.metrics import compute_classification_metrics


class EarlyStopping:
    """Early stops training when monitored validation loss stops improving."""

    def __init__(self, patience: int = 12, min_delta: float = 1e-4):
        self.patience = patience
        self.min_delta = min_delta
        self.counter = 0
        self.best_loss = float("inf")
        self.early_stop = False

    def step(self, val_loss: float) -> bool:
        if val_loss < self.best_loss - self.min_delta:
            self.best_loss = val_loss
            self.counter = 0
            return True  # Improvement achieved
        else:
            self.counter += 1
            if self.counter >= self.patience:
                self.early_stop = True
            return False


def get_optimal_device(force_cpu: bool = False) -> Tuple[torch.device, bool]:
    """Detect hardware and configure RTX 3050 CUDA settings."""
    if not force_cpu and torch.cuda.is_available():
        device = torch.device("cuda")
        gpu_name = torch.cuda.get_device_name(0)
        vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
        print(f"[DEVICE] CUDA Active: {gpu_name} ({vram_gb:.2f} GB VRAM)")
        # Enable CuDNN benchmark for consistent tensor shapes
        torch.backends.cudnn.benchmark = True
        return device, True
    print("[DEVICE] Running on CPU.")
    return torch.device("cpu"), False


def train_csiformer(
    dataset_name: str = "combined",
    target_mode: str = "HT20",
    epochs: int = 100,
    batch_size: Optional[int] = None,
    learning_rate: float = 1e-4,
    weight_decay: float = 1e-2,
    patience: int = 15,
    use_amp: bool = True,
    use_class_weights: bool = False,
    class_weights: Optional[List[float]] = None,
    dry_run: bool = False,
    resume_checkpoint: Optional[str] = None,
    widar_max_samples: Optional[int] = None,
    ntufi_max_samples: Optional[int] = None,
    models_dir: Union[str, Path] = "models",
    reports_dir: Union[str, Path] = "reports",
    log_dir: Union[str, Path] = "logs/csiformer",
    force_cpu: bool = False,
    smoke_test: bool = False
) -> Dict[str, Any]:
    """
    Execute full training loop for CSIFormer.
    """
    models_path = Path(models_dir)
    reports_path = Path(reports_dir)
    log_path = Path(log_dir)

    models_path.mkdir(parents=True, exist_ok=True)
    reports_path.mkdir(parents=True, exist_ok=True)
    log_path.mkdir(parents=True, exist_ok=True)

    device, is_cuda = get_optimal_device(force_cpu=force_cpu)

    # Automatic batch size tuning for RTX 3050 (4 GB VRAM)
    if batch_size is None:
        batch_size = 32 if is_cuda else 16
    print(f"[CONFIG] Batch Size: {batch_size} | Mode: {target_mode} | Epochs: {epochs}")

    # Subcarrier count
    subcarriers = 56 if target_mode.upper() == "HT20" else 114
    seq_len = 50

    # Determine class count
    if dataset_name.lower() in ("widar", "widar3"):
        num_classes = 6
        class_names = [f"Gesture_{i}" for i in range(6)]
    elif dataset_name.lower() in ("ntufi", "ntufi_har"):
        num_classes = 6
        class_names = ["box", "circle", "clean", "fall", "run", "walk"]
    else:
        num_classes = 12
        class_names = CombinedCSIDataset.UNIFIED_CLASSES

    # 1. Create DataLoaders
    print(f"[DATA] Initializing DataLoaders for {dataset_name}...")
    train_loader, val_loader, test_loader = create_dataloaders(
        dataset_name=dataset_name,
        batch_size=batch_size,
        target_mode=target_mode,
        target_timesteps=seq_len,
        widar_max_samples=widar_max_samples,
        ntufi_max_samples=ntufi_max_samples
    )
    print(f"[DATA] Batches: Train={len(train_loader)}, Val={len(val_loader)}, Test={len(test_loader)}")

    # 2. Build Model
    model = CSIFormerNet(
        num_subcarriers=subcarriers,
        seq_len=seq_len,
        num_classes=num_classes,
        embed_dim=128,
        nhead=8,
        num_layers=3,
        dim_feedforward=512,
        dropout=0.1
    ).to(device)

    # 3. Loss Functions & Optimizer
    if use_class_weights:
        if class_weights is not None:
            w_tensor = torch.tensor(class_weights, dtype=torch.float32, device=device)
        else:
            w_tensor = torch.tensor(
                [0.0814, 0.0811, 0.0802, 0.1228, 0.1618, 0.1619, 1.8512, 1.9379, 1.9379, 1.8106, 1.9081, 1.8651],
                dtype=torch.float32,
                device=device
            )
        criterion_activity = nn.CrossEntropyLoss(weight=w_tensor)
        print(f"[LOSS] Balanced CrossEntropyLoss enabled with inverse class weights.")
    else:
        criterion_activity = nn.CrossEntropyLoss()
    criterion_presence = nn.BCEWithLogitsLoss()
    criterion_motion = nn.BCEWithLogitsLoss()

    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=learning_rate,
        weight_decay=weight_decay
    )

    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer,
        T_max=epochs,
        eta_min=1e-6
    )

    # Mixed Precision Scaler
    scaler = torch.amp.GradScaler("cuda", enabled=(use_amp and is_cuda))

    # Early Stopping
    early_stopping = EarlyStopping(patience=patience)

    # TensorBoard
    writer = SummaryWriter(log_dir=str(log_path))

    start_epoch = 1
    best_val_f1 = 0.0
    history: List[Dict[str, Any]] = []

    # Resume from checkpoint if requested
    if resume_checkpoint and Path(resume_checkpoint).exists():
        print(f"[RESUME] Loading checkpoint: {resume_checkpoint}")
        ckpt = torch.load(resume_checkpoint, map_location=device, weights_only=False)
        model.load_state_dict(ckpt["model_state_dict"])
        optimizer.load_state_dict(ckpt["optimizer_state_dict"])
        start_epoch = ckpt.get("epoch", 1) + 1
        best_val_f1 = ckpt.get("best_val_f1", 0.0)

    # Dry-run validation of the entire pipeline
    if dry_run:
        print("\n" + "=" * 75)
        print("[DRY RUN] VALIDATING PRODUCTION TRAINING PIPELINE ON HARDWARE")
        print("=" * 75)
        model.train()
        test_batch = next(iter(train_loader))
        x = test_batch["csi"].to(device, non_blocking=is_cuda)
        y_act = test_batch["label"].to(device, non_blocking=is_cuda)
        y_pres = test_batch["presence"].to(device, non_blocking=is_cuda)
        y_mot = test_batch["motion"].to(device, non_blocking=is_cuda)

        optimizer.zero_grad(set_to_none=True)
        with torch.amp.autocast("cuda", enabled=(use_amp and is_cuda)):
            outputs = model(x)
            act_loss = criterion_activity(outputs["activity_logits"], y_act)
            pres_loss = criterion_presence(outputs["presence_logits"], y_pres)
            mot_loss = criterion_motion(outputs["motion_logits"], y_mot)
            loss = act_loss + 0.2 * pres_loss + 0.2 * mot_loss

        scaler.scale(loss).backward()
        scaler.unscale_(optimizer)
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        scaler.step(optimizer)
        scaler.update()

        print(f"[DRY RUN] Forward/Backward Step Verified | Sample Batch Loss: {loss.item():.4f}")
        print(f"[DRY RUN] Target Device: {device} | Tensor Shape: {list(x.shape)}")
        print(f"[DRY RUN] Dataset Splitting Verified: Train={len(train_loader.dataset)}, Val={len(val_loader.dataset)}, Test={len(test_loader.dataset)}")
        print("[DRY RUN] Pipeline fully validated and verified ready for production training!\n")
        return {
            "status": "dry_run_success",
            "train_samples": len(train_loader.dataset),
            "val_samples": len(val_loader.dataset),
            "test_samples": len(test_loader.dataset),
            "sample_loss": float(loss.item()),
            "device": str(device)
        }

    print("\n" + "=" * 75)
    print("STARTING CSIFORMER TRAINING LOOP")
    print("=" * 75)

    training_start_time = time.time()

    for epoch in range(start_epoch, epochs + 1):
        epoch_start = time.time()
        model.train()

        total_train_loss = 0.0
        train_correct = 0
        train_total = 0

        for batch_idx, batch in enumerate(train_loader):
            x = batch["csi"].to(device, non_blocking=is_cuda)
            y_act = batch["label"].to(device, non_blocking=is_cuda)
            y_pres = batch["presence"].to(device, non_blocking=is_cuda)
            y_mot = batch["motion"].to(device, non_blocking=is_cuda)

            optimizer.zero_grad(set_to_none=True)

            with torch.amp.autocast("cuda", enabled=(use_amp and is_cuda)):
                outputs = model(x)
                act_loss = criterion_activity(outputs["activity_logits"], y_act)
                pres_loss = criterion_presence(outputs["presence_logits"], y_pres)
                mot_loss = criterion_motion(outputs["motion_logits"], y_mot)
                loss = act_loss + 0.2 * pres_loss + 0.2 * mot_loss

            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            scaler.step(optimizer)
            scaler.update()

            total_train_loss += loss.item()
            preds = torch.argmax(outputs["activity_logits"], dim=-1)
            train_correct += (preds == y_act).sum().item()
            train_total += y_act.size(0)

            if (batch_idx + 1) % 25 == 0 or (batch_idx + 1) == len(train_loader):
                pct = ((batch_idx + 1) / len(train_loader)) * 100
                batch_acc = ((preds == y_act).sum().item() / max(1, y_act.size(0))) * 100
                print(f"  [Epoch {epoch:02d}/{epochs:02d} | Batch {batch_idx+1:03d}/{len(train_loader):03d} ({pct:.1f}%)] Loss: {loss.item():.4f} | Acc: {batch_acc:.1f}%", flush=True)

            if smoke_test and batch_idx >= 2:
                break

        scheduler.step()

        train_loss = total_train_loss / max(1, len(train_loader) if not smoke_test else 3)
        train_acc = train_correct / max(1, train_total)

        # 4. Validation Loop
        model.eval()
        total_val_loss = 0.0
        val_preds_list = []
        val_targets_list = []

        with torch.no_grad():
            for batch_idx, batch in enumerate(val_loader):
                x = batch["csi"].to(device, non_blocking=is_cuda)
                y_act = batch["label"].to(device, non_blocking=is_cuda)
                y_pres = batch["presence"].to(device, non_blocking=is_cuda)
                y_mot = batch["motion"].to(device, non_blocking=is_cuda)

                with torch.amp.autocast("cuda", enabled=(use_amp and is_cuda)):
                    outputs = model(x)
                    act_loss = criterion_activity(outputs["activity_logits"], y_act)
                    pres_loss = criterion_presence(outputs["presence_logits"], y_pres)
                    mot_loss = criterion_motion(outputs["motion_logits"], y_mot)
                    loss = act_loss + 0.2 * pres_loss + 0.2 * mot_loss

                total_val_loss += loss.item()
                probs = torch.softmax(outputs["activity_logits"], dim=-1).cpu().numpy()
                val_preds_list.append(probs)
                val_targets_list.append(y_act.cpu().numpy())

                if (batch_idx + 1) % 20 == 0 or (batch_idx + 1) == len(val_loader):
                    pct = ((batch_idx + 1) / len(val_loader)) * 100
                    print(f"  [Epoch {epoch:02d} Val | Batch {batch_idx+1:02d}/{len(val_loader):02d} ({pct:.1f}%)]", flush=True)

                if smoke_test and batch_idx >= 2:
                    break

        # Check if underlying dataset can persist its cache
        if epoch == 1:
            try:
                base_ds = train_loader.dataset.dataset if hasattr(train_loader.dataset, "dataset") else train_loader.dataset
                if hasattr(base_ds, "widar_ds") and hasattr(base_ds.widar_ds, "cache_file"):
                    if not base_ds.widar_ds.cache_file.exists() and len(base_ds.widar_ds.cache) > 0:
                        base_ds.widar_ds.cache_dir.mkdir(parents=True, exist_ok=True)
                        torch.save(base_ds.widar_ds.cache, base_ds.widar_ds.cache_file)
                        print(f"[CACHE] Saved Widar 3.0 cache ({len(base_ds.widar_ds.cache)} tensors) to disk: {base_ds.widar_ds.cache_file.name}", flush=True)
                if hasattr(base_ds, "ntufi_ds") and hasattr(base_ds.ntufi_ds, "cache_file"):
                    if not base_ds.ntufi_ds.cache_file.exists() and len(base_ds.ntufi_ds.cache) > 0:
                        base_ds.ntufi_ds.cache_dir.mkdir(parents=True, exist_ok=True)
                        torch.save(base_ds.ntufi_ds.cache, base_ds.ntufi_ds.cache_file)
                        print(f"[CACHE] Saved NTU-Fi cache ({len(base_ds.ntufi_ds.cache)} tensors) to disk: {base_ds.ntufi_ds.cache_file.name}", flush=True)
            except Exception as e:
                pass

        val_loss = total_val_loss / max(1, len(val_loader) if not smoke_test else 2)
        val_probs_arr = np.concatenate(val_preds_list, axis=0) if val_preds_list else np.zeros((1, num_classes))
        val_targets_arr = np.concatenate(val_targets_list, axis=0) if val_targets_list else np.zeros(1)

        val_metrics = compute_classification_metrics(
            y_true=val_targets_arr,
            y_pred_probs=val_probs_arr,
            class_names=class_names
        )
        val_acc = val_metrics["accuracy"]
        val_f1 = val_metrics["f1_macro"]
        val_prec = val_metrics.get("precision_macro", 0.0)
        val_rec = val_metrics.get("recall_macro", 0.0)

        duration = time.time() - epoch_start
        vram_mb = round(torch.cuda.max_memory_allocated(device=device) / (1024 ** 2), 1) if is_cuda else 0.0

        # TensorBoard logging
        writer.add_scalar("Loss/Train", train_loss, epoch)
        writer.add_scalar("Loss/Val", val_loss, epoch)
        writer.add_scalar("Accuracy/Train", train_acc, epoch)
        writer.add_scalar("Accuracy/Val", val_acc, epoch)
        writer.add_scalar("Precision/Val", val_prec, epoch)
        writer.add_scalar("Recall/Val", val_rec, epoch)
        writer.add_scalar("F1/Val", val_f1, epoch)
        writer.add_scalar("LR", optimizer.param_groups[0]["lr"], epoch)
        writer.add_scalar("VRAM_MB", vram_mb, epoch)

        epoch_record = {
            "epoch": epoch,
            "train_loss": round(train_loss, 4),
            "train_acc": round(train_acc, 4),
            "val_loss": round(val_loss, 4),
            "val_acc": round(val_acc, 4),
            "val_precision": round(val_prec, 4),
            "val_recall": round(val_rec, 4),
            "val_f1": round(val_f1, 4),
            "lr": optimizer.param_groups[0]["lr"],
            "duration_sec": round(duration, 2),
            "vram_mb": vram_mb
        }
        history.append(epoch_record)

        print(
            f"Epoch [{epoch:03d}/{epochs:03d}] | "
            f"Train Loss: {train_loss:.4f} Acc: {train_acc*100:.1f}% | "
            f"Val Loss: {val_loss:.4f} Acc: {val_acc*100:.1f}% Prec: {val_prec*100:.1f}% Rec: {val_rec*100:.1f}% F1: {val_f1:.4f} | "
            f"VRAM: {vram_mb:.1f}MB | Time: {duration:.1f}s"
        )

        # 5. Checkpoint Saving
        active_weights = (
            class_weights if (use_class_weights and class_weights is not None)
            else ([0.0814, 0.0811, 0.0802, 0.1228, 0.1618, 0.1619, 1.8512, 1.9379, 1.9379, 1.8106, 1.9081, 1.8651] if use_class_weights else None)
        )
        checkpoint_dict = {
            "epoch": epoch,
            "model_state_dict": model.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
            "num_subcarriers": subcarriers,
            "seq_len": seq_len,
            "num_classes": num_classes,
            "embed_dim": 128,
            "best_val_f1": best_val_f1,
            "val_metrics": val_metrics,
            "class_weights": active_weights,
            "target_mode": target_mode,
            "dataset_name": dataset_name,
            "model_architecture": "CSIFormerNet",
            "total_parameters": sum(p.numel() for p in model.parameters())
        }

        # Latest checkpoint
        torch.save(checkpoint_dict, models_path / "latest_checkpoint.pth")

        # Best checkpoint
        improved = early_stopping.step(val_loss)
        if val_f1 > best_val_f1 or improved:
            if val_f1 > best_val_f1:
                best_val_f1 = val_f1
            checkpoint_dict["best_val_f1"] = best_val_f1
            torch.save(checkpoint_dict, models_path / "best_csiformer.pth")
            print(f"  --> Saved new best checkpoint (Val F1: {best_val_f1:.4f}) to {models_path / 'best_csiformer.pth'}")

        if early_stopping.early_stop and not smoke_test:
            print(f"[EARLY STOP] Validation loss plateaued for {patience} epochs. Stopping.")
            break

        if smoke_test and epoch >= 2:
            print("[SMOKE TEST] Completed 2 smoke test epochs successfully.")
            break

    total_training_time = time.time() - training_start_time
    writer.close()

    # 6. Generate Reports
    generate_training_report(
        history=history,
        total_time=total_training_time,
        best_f1=best_val_f1,
        save_path=reports_path / "training_report.md",
        dataset_name=dataset_name,
        target_mode=target_mode,
        device=str(device)
    )

    generate_dataset_summary(
        train_loader=train_loader,
        val_loader=val_loader,
        test_loader=test_loader,
        save_path=reports_path / "dataset_summary.md"
    )

    return {
        "status": "COMPLETED",
        "epochs_trained": len(history),
        "total_time_seconds": round(total_training_time, 2),
        "best_val_f1": best_val_f1,
        "history": history
    }


def generate_training_report(
    history: List[Dict[str, Any]],
    total_time: float,
    best_f1: float,
    save_path: Path,
    dataset_name: str,
    target_mode: str,
    device: str
):
    """Render comprehensive markdown training report."""
    last_ep = history[-1] if history else {}
    md = f"""# CSIFormer Training Execution Report

**Execution Timestamp:** {datetime.now(timezone.utc).isoformat()}  
**Compute Hardware:** {device}  
**Dataset Trained:** `{dataset_name}`  
**Hardware Mode:** `{target_mode}` (ESP32-S3 Subcarrier Grid)  
**Total Training Duration:** {total_time:.2f} seconds ({total_time / 60:.1f} minutes)  
**Best Validation F1:** **{best_f1:.4f}**  
**Final Validation Accuracy:** **{last_ep.get("val_acc", 0.0) * 100:.2f}%**  

---

## 1. Hyperparameter Configuration

| Parameter | Value | Rationale |
| :--- | :--- | :--- |
| **Architecture** | CSIFormerNet (CNN + Pre-LN Transformer + Temporal Attention) | Multi-task spatial-temporal learning |
| **Optimizer** | AdamW | Decoupled weight decay regularization |
| **Initial Learning Rate** | 1e-4 | Tuned for stable Transformer convergence |
| **Learning Rate Schedule** | CosineAnnealingLR | Smooth decay towards min LR |
| **Precision** | Automatic Mixed Precision (AMP FP16) | RTX 3050 Tensor Core throughput optimization |
| **Gradient Clipping** | Max Norm = 1.0 | Prevents gradient explosion in self-attention |
| **Loss Function** | $\\mathcal{{L}}_{{\\text{{CE}}}} + 0.2 \\mathcal{{L}}_{{\\text{{Pres}}}} + 0.2 \\mathcal{{L}}_{{\\text{{Mot}}}}$ | Joint activity recognition and motion detection |

---

## 2. Epoch Training Progression

| Epoch | Train Loss | Train Acc | Val Loss | Val Acc | Val Prec | Val Rec | Val F1 | Learning Rate | Duration | VRAM |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
"""
    for rec in history:
        md += (
            f"| {rec['epoch']:02d} | {rec['train_loss']:.4f} | {rec['train_acc']*100:.1f}% | "
            f"{rec['val_loss']:.4f} | {rec['val_acc']*100:.1f}% | {rec.get('val_precision', 0.0)*100:.1f}% | "
            f"{rec.get('val_recall', 0.0)*100:.1f}% | {rec['val_f1']:.4f} | {rec['lr']:.2e} | "
            f"{rec['duration_sec']}s | {rec.get('vram_mb', 0.0):.1f}MB |\n"
        )

    md += """
---

## 3. Checkpoint Deliverables

- Best Model Checkpoint: `models/best_csiformer.pth`
- Latest Epoch Checkpoint: `models/latest_checkpoint.pth`
"""
    with open(save_path, "w", encoding="utf-8") as f:
        f.write(md)


def generate_dataset_summary(
    train_loader,
    val_loader,
    test_loader,
    save_path: Path
):
    """Render markdown dataset summary."""
    train_samples = len(train_loader.dataset)
    val_samples = len(val_loader.dataset)
    test_samples = len(test_loader.dataset)
    total = train_samples + val_samples + test_samples

    md = f"""# CSIFormer Dataset Training Summary

**Generated At:** {datetime.now(timezone.utc).isoformat()}  
**Total Samples in Split:** {total}  

| Partition | Sample Count | Percentage of Dataset |
| :--- | :---: | :---: |
| **Training Set** | {train_samples} | {train_samples / total * 100:.1f}% |
| **Validation Set** | {val_samples} | {val_samples / total * 100:.1f}% |
| **Testing Set** | {test_samples} | {test_samples / total * 100:.1f}% |
| **TOTAL** | **{total}** | **100.0%** |
"""
    with open(save_path, "w", encoding="utf-8") as f:
        f.write(md)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train CSIFormer Model")
    parser.add_argument("--config", type=str, default=None, help="Path to production training configuration JSON")
    parser.add_argument("--dataset", type=str, default="combined", help="Dataset: combined, widar, or ntufi")
    parser.add_argument("--target_mode", type=str, default="HT20", help="ESP32 mode: HT20 or HT40")
    parser.add_argument("--epochs", type=int, default=100, help="Total epochs")
    parser.add_argument("--batch_size", type=int, default=None, help="Batch size (auto-tuned if omitted)")
    parser.add_argument("--lr", type=float, default=1e-4, help="Learning rate")
    parser.add_argument("--patience", type=int, default=15, help="Early stopping patience")
    parser.add_argument("--device", type=str, default=None, help="Device: cuda or cpu")
    parser.add_argument("--resume", type=str, default=None, help="Path to checkpoint to resume from")
    parser.add_argument("--smoke_test", action="store_true", help="Run 2 quick smoke test epochs")
    parser.add_argument("--dry_run", action="store_true", help="Validate pipeline without running full training epochs")
    parser.add_argument("--use_class_weights", action="store_true", help="Apply inverse frequency class weights")
    parser.add_argument("--widar_max_samples", type=int, default=None, help="Subsample limit for Widar")
    parser.add_argument("--ntufi_max_samples", type=int, default=None, help="Subsample limit for NTU-Fi")

    args = parser.parse_args()

    dataset_name = args.dataset
    target_mode = args.target_mode
    epochs = args.epochs
    batch_size = args.batch_size
    lr = args.lr
    patience = args.patience
    use_class_weights = args.use_class_weights
    class_weights = None
    widar_max = args.widar_max_samples
    ntufi_max = args.ntufi_max_samples
    models_dir = "models"
    reports_dir = "reports"
    log_dir = "logs/csiformer"

    if args.config and Path(args.config).exists():
        print(f"[CONFIG] Loading training parameters from: {args.config}")
        with open(args.config, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        ds_cfg = cfg.get("dataset", {})
        opt_cfg = cfg.get("optimization", {})
        bal_cfg = cfg.get("class_balancing", {})
        paths_cfg = cfg.get("paths", {})

        dataset_name = ds_cfg.get("dataset_name", dataset_name)
        target_mode = ds_cfg.get("target_mode", target_mode)
        batch_size = ds_cfg.get("batch_size", batch_size)
        epochs = opt_cfg.get("epochs", epochs)
        lr = opt_cfg.get("learning_rate", lr)
        patience = opt_cfg.get("early_stopping_patience", patience)
        use_class_weights = bal_cfg.get("use_class_weights", use_class_weights)
        class_weights = bal_cfg.get("class_weights", None)
        widar_max = ds_cfg.get("widar_max_samples", widar_max)
        ntufi_max = ds_cfg.get("ntufi_max_samples", ntufi_max)
        models_dir = paths_cfg.get("models_dir", models_dir)
        reports_dir = paths_cfg.get("reports_dir", reports_dir)
        log_dir = paths_cfg.get("log_dir", log_dir)

    train_csiformer(
        dataset_name=dataset_name,
        target_mode=target_mode,
        epochs=epochs,
        batch_size=batch_size,
        learning_rate=lr,
        patience=patience,
        resume_checkpoint=args.resume,
        use_class_weights=use_class_weights,
        class_weights=class_weights,
        dry_run=args.dry_run,
        widar_max_samples=widar_max,
        ntufi_max_samples=ntufi_max,
        models_dir=models_dir,
        reports_dir=reports_dir,
        log_dir=log_dir,
        smoke_test=args.smoke_test,
        force_cpu=(args.device == "cpu")
    )
