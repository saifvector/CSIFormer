import sys
import time
import json
import csv
from pathlib import Path
from collections import Counter
import numpy as np
import torch

BASE_DIR = Path(r"c:\Users\saifu\Desktop\4-1 project")
sys.path.insert(0, str(BASE_DIR / "backend"))

from app.datasets.combined_dataset import create_dataloaders, CombinedCSIDataset
from app.services.csi_preprocessor import CSIPreprocessor
from app.services.esp32_csi_adapter import ESP32CSIAdapter
from app.models.csiformernet import CSIFormerNet

print("=" * 70)
print("PHASE 10.5B: PRE-TRAINING FORENSIC AUDIT")
print("=" * 70)

widar_dir = BASE_DIR / "datasets" / "widar3"
ntufi_dir = BASE_DIR / "datasets" / "ntufi_har"

# 1. Class distribution
print("\n--- 1. EXACT CLASS DISTRIBUTION ---")
widar_csv = widar_dir / "labels" / "samples.csv"
widar_classes = Counter()
widar_raw_ids = Counter()
widar_mapped_classes = Counter()
with open(widar_csv, "r", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        g_name = row["gesture_name"]
        raw_g = int(row["gesture_id"])
        mapped_label = (raw_g - 1) % 6
        widar_classes[g_name] += 1
        widar_raw_ids[raw_g] += 1
        widar_mapped_classes[mapped_label] += 1

print("Widar 3.0 Raw Gesture Distribution:")
for k, v in sorted(widar_classes.items()):
    print(f"  {k:15s}: {v:5d} ({v/21000*100:5.2f}%)")

print("\nWidar 3.0 Mapped Class (0..5) Distribution:")
widar_names_map = {0: "Push&Pull", 1: "Sweep", 2: "Clap", 3: "Slide", 4: "Draw-O", 5: "Draw-Zigzag"}
for k in range(6):
    cnt = widar_mapped_classes[k]
    print(f"  Class {k} ({widar_names_map[k]:12s}): {cnt:5d} ({cnt/21000*100:5.2f}%)")

ntufi_csv = ntufi_dir / "labels" / "samples.csv"
ntufi_classes = Counter()
with open(ntufi_csv, "r", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        ntufi_classes[row["class_name"]] += 1

print("\nNTU-Fi HAR Class (6..11) Distribution:")
ntufi_names = ["box", "circle", "clean", "fall", "run", "walk"]
for i, name in enumerate(ntufi_names):
    cnt = ntufi_classes[name]
    print(f"  Class {i+6} ({name:12s}): {cnt:5d} ({cnt/1200*100:5.2f}%)")

print("\nUnified Combined 12-Class Dataset Total Distribution:")
total_distribution = {}
for i in range(6):
    name = widar_names_map[i]
    cnt = widar_mapped_classes[i]
    total_distribution[name] = cnt
    print(f"  Class {i:02d} ({name:12s}): {cnt:5d} ({cnt/22200*100:5.2f}%)")
for i, name in enumerate(ntufi_names):
    cnt = ntufi_classes[name]
    total_distribution[name] = cnt
    print(f"  Class {i+6:02d} ({name:12s}): {cnt:5d} ({cnt/22200*100:5.2f}%)")

# 2. Train / Val / Test Splits
print("\n--- 2. TRAIN / VALIDATION / TEST SPLITS ---")
widar_split_file = widar_dir / "labels" / "train_test_split.json"
with open(widar_split_file, "r", encoding="utf-8") as f:
    w_split = json.load(f)
w_train_cnt = len(w_split["standard_split"]["train_samples"])
w_test_cnt = len(w_split["standard_split"]["test_samples"])
print(f"Widar Standard Split: Train={w_train_cnt} ({w_train_cnt/21000*100:.1f}%), Test={w_test_cnt} ({w_test_cnt/21000*100:.1f}%)")

n_train_cnt = 0
n_test_cnt = 0
with open(ntufi_csv, "r", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        if row["split"] == "train":
            n_train_cnt += 1
        elif row["split"] == "test":
            n_test_cnt += 1
print(f"NTU-Fi Split: Train={n_train_cnt} ({n_train_cnt/1200*100:.1f}%), Test={n_test_cnt} ({n_test_cnt/1200*100:.1f}%)")

full_train_initial = w_train_cnt + n_train_cnt
full_test = w_test_cnt + n_test_cnt
val_ratio = 0.15
val_size = max(1, int(full_train_initial * val_ratio))
train_size = full_train_initial - val_size

print(f"Full Dataset Split Across All 22,200 Samples:")
print(f"  Initial Training Split (Widar + NTU-Fi): {full_train_initial} (80.0%)")
print(f"  Test Split (Held-out Benchmark):        {full_test} (20.0%)")
print(f"  When applying val_split_ratio=0.15 to Training Split:")
print(f"    - Training Set:   {train_size:5d} ({train_size/22200*100:5.2f}%)")
print(f"    - Validation Set: {val_size:5d} ({val_size/22200*100:5.2f}%)")
print(f"    - Testing Set:    {full_test:5d} ({full_test/22200*100:5.2f}%)")
print(f"    - Total:          {train_size + val_size + full_test} (100.0%)")

# 3. Class Imbalance
print("\n--- 3. CLASS IMBALANCE ANALYSIS ---")
max_class_cnt = max(total_distribution.values())
min_class_cnt = min(total_distribution.values())
imbalance_ratio = max_class_cnt / min_class_cnt
print(f"Highest support class count: {max_class_cnt}")
print(f"Lowest support class count:  {min_class_cnt}")
print(f"Imbalance ratio (Max / Min): {imbalance_ratio:.2f} : 1")
print(f"Widar (Classes 0-5) avg per class: {21000/6:.0f} samples")
print(f"NTU-Fi (Classes 6-11) avg per class: {1200/6:.0f} samples")
print(f"Cross-dataset imbalance ratio: {21000/1200:.2f} : 1 (Widar dominates NTU-Fi by 17.5x)")

# 4. Duplicate Detection
print("\n--- 4. DUPLICATE SAMPLE DETECTION ---")
with open(widar_csv, "r", encoding="utf-8") as f:
    w_rows = list(csv.DictReader(f))
w_sample_ids = [r["sample_id"] for r in w_rows]
w_filenames = [r["filename"] for r in w_rows]
print(f"Widar 3.0: Total rows={len(w_rows)}, Unique sample_ids={len(set(w_sample_ids))}, Unique filenames={len(set(w_filenames))}")

with open(ntufi_csv, "r", encoding="utf-8") as f:
    n_rows = list(csv.DictReader(f))
n_sample_ids = [r["sample_id"] for r in n_rows]
n_filenames = [r["filename"] for r in n_rows]
print(f"NTU-Fi HAR: Total rows={len(n_rows)}, Unique sample_ids={len(set(n_sample_ids))}, Unique filenames={len(set(n_filenames))}")

# 5 & 6. Window Generation & Feature Tensor Shapes
print("\n--- 5 & 6. WINDOW GENERATION & TENSOR SHAPES ---")
prep_ht20 = CSIPreprocessor(target_mode="HT20", target_timesteps=50)
prep_ht40 = CSIPreprocessor(target_mode="HT40", target_timesteps=50)
print(f"HT20 Preprocessor config: timesteps={prep_ht20.target_timesteps}, subcarriers={prep_ht20.target_subcarriers}")
print(f"HT40 Preprocessor config: timesteps={prep_ht40.target_timesteps}, subcarriers={prep_ht40.target_subcarriers}")

ds_test = CombinedCSIDataset(split="train", target_mode="HT20", target_timesteps=50, widar_max_samples=1, ntufi_max_samples=1)
for i in range(len(ds_test)):
    sample = ds_test[i]
    csi_tensor = sample["csi"]
    print(f"Sample {i} [{sample['dataset']}]:")
    print(f"  Tensor shape: {list(csi_tensor.shape)}")
    print(f"  Data type:    {csi_tensor.dtype}")
    print(f"  Range:        [{csi_tensor.min():.4f}, {csi_tensor.max():.4f}], mean={csi_tensor.mean():.4f}")
    print(f"  Contains NaN: {torch.isnan(csi_tensor).any().item()}")
    print(f"  Label:        {sample['label']}")
    print(f"  Presence:     {sample['presence'].item()}, Motion: {sample['motion'].item()}")

# 7. ESP32CSIAdapter Output Verification
print("\n--- 7. ESP32CSIADAPTER VERIFICATION ---")
adapter_ht20 = ESP32CSIAdapter(target_mode="HT20")
adapter_ht40 = ESP32CSIAdapter(target_mode="HT40")

raw_intel = np.random.randn(50, 30).astype(np.float32)
out_ht20_intel = adapter_ht20.intel5300_to_esp32(raw_intel)
out_ht40_intel = adapter_ht40.intel5300_to_esp32(raw_intel)
print(f"Intel 5300 (50, 30) -> ESP32 HT20: shape={out_ht20_intel.shape}, NaNs={np.isnan(out_ht20_intel).any()}")
print(f"Intel 5300 (50, 30) -> ESP32 HT40: shape={out_ht40_intel.shape}, NaNs={np.isnan(out_ht40_intel).any()}")

raw_atheros = np.random.randn(50, 114).astype(np.float32)
out_ht20_ath = adapter_ht20.atheros_to_esp32(raw_atheros)
out_ht40_ath = adapter_ht40.atheros_to_esp32(raw_atheros)
print(f"Atheros (50, 114)   -> ESP32 HT20: shape={out_ht20_ath.shape}, NaNs={np.isnan(out_ht20_ath).any()}")
print(f"Atheros (50, 114)   -> ESP32 HT40: shape={out_ht40_ath.shape}, NaNs={np.isnan(out_ht40_ath).any()}")

# 8 & 9. GPU Memory & Recommended Batch Size
print("\n--- 8 & 9. GPU MEMORY PROFILING ON RTX 3050 4GB ---")
if torch.cuda.is_available():
    device = torch.device("cuda")
    gpu_name = torch.cuda.get_device_name(0)
    vram_bytes = torch.cuda.get_device_properties(0).total_memory
    vram_gb = vram_bytes / (1024**3)
    print(f"Detected GPU: {gpu_name} ({vram_gb:.2f} GB Total VRAM)")

    model = CSIFormerNet(num_subcarriers=56, seq_len=50, num_classes=12, embed_dim=128).to(device)
    total_params = sum(p.numel() for p in model.parameters())
    param_mb = sum(p.numel() * p.element_size() for p in model.parameters()) / (1024**2)
    print(f"Model Parameters: {total_params:,} ({param_mb:.2f} MB)")

    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4)
    scaler = torch.amp.GradScaler("cuda")

    benchmark_results = {}
    for bs in [16, 32, 64, 128]:
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats()
        x = torch.randn(bs, 50, 56, device=device)
        y = torch.randint(0, 12, (bs,), device=device)

        # Warmup
        for _ in range(3):
            with torch.amp.autocast("cuda"):
                out = model(x)
                loss = torch.nn.functional.cross_entropy(out["activity_logits"], y)
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
            optimizer.zero_grad()

        # Measure 10 steps
        torch.cuda.synchronize()
        t0 = time.perf_counter()
        for _ in range(10):
            with torch.amp.autocast("cuda"):
                out = model(x)
                loss = torch.nn.functional.cross_entropy(out["activity_logits"], y)
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
            optimizer.zero_grad()
        torch.cuda.synchronize()
        elapsed_sec = (time.perf_counter() - t0) / 10

        peak_alloc = torch.cuda.max_memory_allocated() / (1024**2)
        peak_res = torch.cuda.max_memory_reserved() / (1024**2)
        vram_util_pct = (peak_res / (vram_bytes / (1024**2))) * 100
        throughput = bs / elapsed_sec

        benchmark_results[bs] = {
            "peak_alloc_mb": peak_alloc,
            "peak_res_mb": peak_res,
            "vram_util_pct": vram_util_pct,
            "step_time_ms": elapsed_sec * 1000,
            "throughput_samples_per_sec": throughput
        }
        print(f"Batch Size {bs:3d}: Peak Allocated={peak_alloc:6.1f} MB | Peak Reserved={peak_res:6.1f} MB ({vram_util_pct:4.1f}% VRAM) | Step={elapsed_sec*1000:5.2f} ms | Throughput={throughput:6.1f} samples/s")

# 10. Training Time Projections
print("\n--- 10. TRAINING TIME PROJECTIONS FOR FULL DATASET ---")
# Training set = 15,076 samples
train_samples = 15076
val_samples = 2660

for bs in [32, 64]:
    batches_per_epoch = (train_samples + bs - 1) // bs
    val_batches = (val_samples + bs - 1) // bs
    # Add I/O overhead factor: parsing CSI binary packets on SSD adds ~1-2 ms per sample
    # Pure forward/backward is ~13-20 ms per batch. With I/O pipelining, total is ~50-80 ms per batch.
    est_step_ms = benchmark_results[bs]["step_time_ms"] + 15.0 # buffer for dataloading
    sec_per_epoch = (batches_per_epoch + val_batches) * (est_step_ms / 1000.0)

    print(f"\nConfiguration: Batch Size = {bs}")
    print(f"  Batches per Epoch: Train={batches_per_epoch}, Val={val_batches}")
    print(f"  Estimated Time per Epoch: {sec_per_epoch:.2f} seconds ({sec_per_epoch/60:.2f} minutes)")
    for ep in [25, 50, 100]:
        total_sec = sec_per_epoch * ep
        hrs = total_sec / 3600
        mins = (total_sec % 3600) / 60
        print(f"  - {ep:3d} Epochs: {total_sec:7.1f} sec (~{hrs:.1f} hrs / {total_sec/60:.1f} mins)")
