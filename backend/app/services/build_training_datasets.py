"""
Automated Training Dataset Acquisition and Engineering Pipeline for CSIFormer.

Strictly adheres to:
- Storage budget: < 20 GB ideal.
- Targeted subsets: Selected high-diversity Widar 3.0 raw CSI + NTU-Fi HAR benchmark.
- Complete exclusion of non-ML assets (BVP, Gait, videos, toolboxes, docs).
- Standardized directory layout and research report generation.
"""

import os
import sys
import json
import csv
import hashlib
import shutil
import zipfile
import re
from pathlib import Path
from typing import Dict, List, Any, Optional
import requests

# Try importing gdown from current python or venv
try:
    import gdown
except ImportError:
    # If in global python without gdown, attempt to use .venv's gdown
    gdown = None


BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
DATASETS_DIR = BASE_DIR / "datasets"

WIDAR_DIR = DATASETS_DIR / "widar3"
WIDAR_CSI_DIR = WIDAR_DIR / "csi"
WIDAR_LABELS_DIR = WIDAR_DIR / "labels"
WIDAR_META_DIR = WIDAR_DIR / "metadata"

NTUFI_DIR = DATASETS_DIR / "ntufi_har"
NTUFI_CSI_DIR = NTUFI_DIR / "csi"
NTUFI_LABELS_DIR = NTUFI_DIR / "labels"
NTUFI_META_DIR = NTUFI_DIR / "metadata"

REPORTS_DIR = DATASETS_DIR / "reports"

# Tsinghua Cloud Seafile Token for Widar 3.0
TSINGHUA_TOKEN = "2760bb9557ca4d09a74d"
TSINGHUA_BASE_DL = f"https://cloud.tsinghua.edu.cn/d/{TSINGHUA_TOKEN}/files/?p=/CSI/{{zip_name}}&dl=1"

# Selected representative subsets of Widar 3.0 raw CSI:
# Perfectly covers 5 subjects, 6 gestures, 5 locations, 5 orientations, 6 receivers.
# Total compressed payload: ~7.21 GB.
WIDAR_SELECTED_ARCHIVES = [
    {"name": "20181128.zip", "size_gb": 0.96, "desc": "User 6 (all 6 gestures, 5 locations, 5 orientations, 6 RX)"},
    {"name": "20181117.zip", "size_gb": 1.32, "desc": "User 4 (all 6 gestures, 5 locations, 5 orientations, 6 RX)"},
    {"name": "20181208.zip", "size_gb": 1.48, "desc": "Users 2 & 3 (multi-subject benchmark)"},
    {"name": "20181209.zip", "size_gb": 1.51, "desc": "Users 2 & 6 (cross-environment validation)"},
    {"name": "20181204.zip", "size_gb": 1.94, "desc": "User 1 (baseline comprehensive spatial session)"},
]

# Google Drive ID for NTU-Fi HAR
NTUFI_GDRIVE_ID = "1DszE7byFzlpyI9gZvmVn51fTr8L1iZaI"

GESTURE_MAP = {
    "1": "Push&Pull",
    "2": "Sweep",
    "3": "Clap",
    "4": "Slide",
    "5": "Draw-O",
    "6": "Draw-Zigzag"
}

NTUFI_CLASSES = ["box", "circle", "clean", "fall", "run", "walk"]


def download_file_stream(url: str, output_path: Path, desc: str = ""):
    """Download a file using streaming chunks with progress updates."""
    print(f"[DOWNLOAD] Starting: {desc} -> {output_path.name}")
    response = requests.get(url, stream=True, allow_redirects=True)
    if response.status_code != 200:
        raise RuntimeError(f"Failed to download {url}, status code: {response.status_code}")

    total_size = int(response.headers.get("content-length", 0))
    chunk_size = 1024 * 1024  # 1 MB
    downloaded = 0

    with open(output_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=chunk_size):
            if chunk:
                f.write(chunk)
                downloaded += len(chunk)
                if total_size > 0:
                    pct = (downloaded / total_size) * 100
                    mb = downloaded / (1024 * 1024)
                    tot_mb = total_size / (1024 * 1024)
                    print(f"\r[DOWNLOAD] {desc}: {mb:.1f}/{tot_mb:.1f} MB ({pct:.1f}%)", end="", flush=True)
                else:
                    mb = downloaded / (1024 * 1024)
                    print(f"\r[DOWNLOAD] {desc}: {mb:.1f} MB", end="", flush=True)
    print()
    print(f"[DOWNLOAD] Finished: {output_path.name} ({downloaded / (1024 * 1024):.1f} MB)")


def extract_widar_archive(zip_path: Path, target_dir: Path) -> int:
    """
    Extract ONLY .dat raw CSI files from a Widar zip archive.
    Ignores all other file types, scripts, and documentation.
    """
    print(f"[EXTRACT] Extracting raw .dat files from {zip_path.name}...")
    extracted_count = 0
    with zipfile.ZipFile(zip_path, "r") as zf:
        for member in zf.infolist():
            if member.filename.endswith(".dat"):
                # Flatten the filename into target_dir
                filename = Path(member.filename).name
                dest_file = target_dir / filename
                if not dest_file.exists():
                    with zf.open(member) as source, open(dest_file, "wb") as target:
                        shutil.copyfileobj(source, target)
                    extracted_count += 1
                else:
                    extracted_count += 1
    print(f"[EXTRACT] Extracted {extracted_count} .dat files from {zip_path.name}")
    return extracted_count


def process_widar_dataset():
    """Acquire, extract, prune, and label Widar 3.0 raw CSI subset."""
    print("=" * 70)
    print("STEP 1: WIDAR 3.0 RAW CSI ACQUISITION & PROCESSING")
    print("=" * 70)

    WIDAR_CSI_DIR.mkdir(parents=True, exist_ok=True)
    WIDAR_LABELS_DIR.mkdir(parents=True, exist_ok=True)
    WIDAR_META_DIR.mkdir(parents=True, exist_ok=True)

    # Check if Widar 3.0 data already extracted
    existing_dat = list(WIDAR_CSI_DIR.glob("*.dat"))
    if len(existing_dat) >= 20000:
        print(f"[WIDAR] Already extracted ({len(existing_dat)} .dat files found). Skipping archive download.")
        generate_widar_labels_and_metadata()
        return

    temp_zip_dir = BASE_DIR / "temp_downloads"
    temp_zip_dir.mkdir(exist_ok=True)

    total_extracted = 0
    for archive in WIDAR_SELECTED_ARCHIVES:
        zip_name = archive["name"]
        dl_url = TSINGHUA_BASE_DL.format(zip_name=zip_name)
        zip_path = temp_zip_dir / zip_name

        # Check if already partially extracted
        print(f"\nProcessing Widar archive: {zip_name} ({archive['desc']})")
        if not zip_path.exists():
            download_file_stream(dl_url, zip_path, desc=zip_name)

        count = extract_widar_archive(zip_path, WIDAR_CSI_DIR)
        total_extracted += count

        # Prune temporary zip immediately to save disk space
        if zip_path.exists():
            print(f"[PRUNE] Removing temporary archive {zip_name} to preserve storage budget.")
            os.remove(zip_path)

    # Clean up temp_zip_dir if empty
    try:
        temp_zip_dir.rmdir()
    except Exception:
        pass

    print(f"[WIDAR] Total raw CSI files in repository: {len(list(WIDAR_CSI_DIR.glob('*.dat')))}")

    # Index labels and metadata
    generate_widar_labels_and_metadata()


def generate_widar_labels_and_metadata():
    """Parse all .dat filenames into structured CSV and JSON split records."""
    print("[WIDAR] Indexing labels and metadata...")
    dat_files = sorted(WIDAR_CSI_DIR.glob("*.dat"))
    
    # Pattern: user{U}-{G}-{LOC}-{ORI}-{REP}-r{RX}.dat
    pattern = re.compile(r"user(\d+)-(\d+)-(\d+)-(\d+)-(\d+)-r(\d+)\.dat")
    
    samples = []
    users = set()
    gestures = set()
    locations = set()
    orientations = set()
    receivers = set()

    for path in dat_files:
        m = pattern.match(path.name)
        if m:
            u, g, loc, ori, rep, rx = m.groups()
            users.add(int(u))
            gestures.add(int(g))
            locations.add(int(loc))
            orientations.add(int(ori))
            receivers.add(int(rx))

            samples.append({
                "sample_id": path.stem,
                "filename": path.name,
                "user_id": int(u),
                "gesture_id": int(g),
                "gesture_name": GESTURE_MAP.get(g, f"Gesture_{g}"),
                "location_id": int(loc),
                "orientation_id": int(ori),
                "repetition_id": int(rep),
                "receiver_id": int(rx),
                "filepath": str(path.relative_to(BASE_DIR)).replace("\\", "/"),
                "file_size_bytes": path.stat().st_size
            })

    # Save samples CSV
    csv_path = WIDAR_LABELS_DIR / "samples.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "sample_id", "filename", "user_id", "gesture_id", "gesture_name",
            "location_id", "orientation_id", "repetition_id", "receiver_id",
            "filepath", "file_size_bytes"
        ])
        writer.writeheader()
        writer.writerows(samples)
    print(f"[WIDAR] Saved {len(samples)} indexed samples to {csv_path}")

    # Generate Train/Test Splits:
    # 1. Standard 80/20 Stratified Split
    # 2. Cross-Subject Split (Train on Users 1, 2, 3, 4; Test on User 6)
    np_samples = np_sample_ids = [s["sample_id"] for s in samples]
    train_ids = []
    test_ids = []
    cross_subject_train = []
    cross_subject_test = []

    for s in samples:
        # Cross-subject split
        if s["user_id"] == 6:
            cross_subject_test.append(s["sample_id"])
        else:
            cross_subject_train.append(s["sample_id"])

        # Standard 80/20 split based on repetition ID
        if s["repetition_id"] % 5 == 0:
            test_ids.append(s["sample_id"])
        else:
            train_ids.append(s["sample_id"])

    splits = {
        "standard_split": {
            "train_count": len(train_ids),
            "test_count": len(test_ids),
            "train_samples": train_ids,
            "test_samples": test_ids
        },
        "cross_subject_split": {
            "train_users": [1, 2, 3, 4],
            "test_users": [6],
            "train_count": len(cross_subject_train),
            "test_count": len(cross_subject_test),
            "train_samples": cross_subject_train,
            "test_samples": cross_subject_test
        }
    }

    split_path = WIDAR_LABELS_DIR / "train_test_split.json"
    with open(split_path, "w", encoding="utf-8") as f:
        json.dump(splits, f, indent=2)
    print(f"[WIDAR] Saved split definitions to {split_path}")

    # Save metadata config
    meta = {
        "dataset_name": "Widar 3.0 (Selected Raw CSI Subset)",
        "source": "Tsinghua University TNS Lab / Seafile Cloud",
        "format": "Intel 5300 NIC Binary (.dat)",
        "subcarriers": 30,
        "antennas": "1 TX x 3 RX per link",
        "sample_rate_hz": 1000,
        "total_samples": len(samples),
        "total_storage_mb": sum(s["file_size_bytes"] for s in samples) / (1024 * 1024),
        "subjects": sorted(list(users)),
        "gestures": {k: GESTURE_MAP.get(str(k), f"Gesture_{k}") for k in sorted(list(gestures))},
        "locations": sorted(list(locations)),
        "orientations": sorted(list(orientations)),
        "receivers": sorted(list(receivers)),
        "target_capabilities": [
            "Human Motion Detection",
            "Human Activity Recognition (6 gestures)",
            "Indoor Spatial Awareness (5 locations, 5 orientations)",
            "Cross-Subject Generalization",
            "Multi-Link Spatial Tracking (6 RX)"
        ]
    }
    meta_path = WIDAR_META_DIR / "config.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    print(f"[WIDAR] Saved metadata specification to {meta_path}")


def process_ntufi_dataset():
    """Acquire, extract, and index the NTU-Fi HAR benchmark dataset."""
    print("\n" + "=" * 70)
    print("STEP 2: NTU-FI HAR DATASET ACQUISITION & PROCESSING")
    print("=" * 70)

    NTUFI_CSI_DIR.mkdir(parents=True, exist_ok=True)
    NTUFI_LABELS_DIR.mkdir(parents=True, exist_ok=True)
    NTUFI_META_DIR.mkdir(parents=True, exist_ok=True)

    temp_zip = BASE_DIR / "NTU-Fi_HAR.zip"

    # Check if NTU-Fi data already extracted
    existing_mat = list(NTUFI_CSI_DIR.glob("**/*.mat"))
    if len(existing_mat) >= 1200:
        print(f"[NTU-FI] Already extracted ({len(existing_mat)} .mat files found).")
    else:
        print("[NTU-FI] Downloading official NTU-Fi HAR benchmark via Google Drive...")
        # Use gdown
        import subprocess
        venv_gdown = BASE_DIR / ".venv" / "Scripts" / "gdown.exe"
        cmd = [str(venv_gdown), NTUFI_GDRIVE_ID, "-O", str(temp_zip)]
        print(f"[NTU-FI] Running command: {' '.join(cmd)}")
        result = subprocess.run(cmd)
        if result.returncode != 0:
            raise RuntimeError(f"Failed to download NTU-Fi HAR with gdown, exit code {result.returncode}")

        print(f"[NTU-FI] Extracting {temp_zip.name}...")
        with zipfile.ZipFile(temp_zip, "r") as zf:
            for member in zf.infolist():
                # Extract only train_amp and test_amp .mat files
                if member.filename.endswith(".mat"):
                    # Maintain subdirectory structure (e.g. train_amp/box/1.mat)
                    parts = Path(member.filename).parts
                    # Find where train_amp or test_amp starts
                    if "train_amp" in parts or "test_amp" in parts:
                        split_idx = parts.index("train_amp") if "train_amp" in parts else parts.index("test_amp")
                        rel_dest = Path(*parts[split_idx:])
                        target_file = NTUFI_CSI_DIR / rel_dest
                        target_file.parent.mkdir(parents=True, exist_ok=True)
                        with zf.open(member) as src, open(target_file, "wb") as dst:
                            shutil.copyfileobj(src, dst)

        # Delete temp zip to save disk space
        if temp_zip.exists():
            print("[PRUNE] Removing NTU-Fi_HAR.zip to save disk space.")
            os.remove(temp_zip)

    # Index labels and metadata
    generate_ntufi_labels_and_metadata()


def generate_ntufi_labels_and_metadata():
    """Index all NTU-Fi HAR .mat files into structured CSV and JSON split records."""
    print("[NTU-FI] Indexing labels and metadata...")
    mat_files = sorted(NTUFI_CSI_DIR.glob("**/*.mat"))

    samples = []
    train_ids = []
    test_ids = []

    for path in mat_files:
        # Expected relative path: train_amp/box/xx.mat or test_amp/box/xx.mat
        rel_parts = path.relative_to(NTUFI_CSI_DIR).parts
        if len(rel_parts) >= 2:
            split_dir = rel_parts[0]  # train_amp or test_amp
            class_name = rel_parts[1]  # box, circle, etc.
            split = "train" if "train" in split_dir else "test"
            class_id = NTUFI_CLASSES.index(class_name) if class_name in NTUFI_CLASSES else -1

            sample_id = f"{split}_{class_name}_{path.stem}"
            if split == "train":
                train_ids.append(sample_id)
            else:
                test_ids.append(sample_id)

            samples.append({
                "sample_id": sample_id,
                "split": split,
                "class_name": class_name,
                "class_id": class_id,
                "filename": path.name,
                "filepath": str(path.relative_to(BASE_DIR)).replace("\\", "/"),
                "file_size_bytes": path.stat().st_size
            })

    # Save samples CSV
    csv_path = NTUFI_LABELS_DIR / "samples.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "sample_id", "split", "class_name", "class_id", "filename", "filepath", "file_size_bytes"
        ])
        writer.writeheader()
        writer.writerows(samples)
    print(f"[NTU-FI] Saved {len(samples)} indexed samples to {csv_path}")

    # Save Train/Test Split
    splits = {
        "official_split": {
            "train_count": len(train_ids),
            "test_count": len(test_ids),
            "train_samples": train_ids,
            "test_samples": test_ids
        }
    }
    split_path = NTUFI_LABELS_DIR / "train_test_split.json"
    with open(split_path, "w", encoding="utf-8") as f:
        json.dump(splits, f, indent=2)
    print(f"[NTU-FI] Saved split definitions to {split_path}")

    # Save metadata config
    meta = {
        "dataset_name": "NTU-Fi HAR Benchmark",
        "source": "SenseFi / Nanyang Technological University",
        "format": "Atheros CSI Tool MATLAB Matrix (.mat)",
        "subcarriers": 114,
        "antennas": "3 RX antennas",
        "time_packets": 500,
        "sample_rate_hz": 100,
        "classes": NTUFI_CLASSES,
        "total_samples": len(samples),
        "train_samples": len(train_ids),
        "test_samples": len(test_ids),
        "total_storage_mb": sum(s["file_size_bytes"] for s in samples) / (1024 * 1024),
        "target_capabilities": [
            "Human Activity Recognition (6 activities: box, circle, clean, fall, run, walk)",
            "Fall Detection Benchmark",
            "Cross-Hardware Benchmarking"
        ]
    }
    meta_path = NTUFI_META_DIR / "config.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    print(f"[NTU-FI] Saved metadata specification to {meta_path}")


def generate_all_reports():
    """Generate dataset_inventory.csv, dataset_statistics.csv, dataset_manifest.json, and dataset_report.md."""
    print("\n" + "=" * 70)
    print("STEP 3: GENERATING RESEARCH INVENTORY, STATISTICS & AUDIT REPORTS")
    print("=" * 70)

    try:
        from generate_dataset_reports import run_full_report_generation
    except ImportError:
        from app.services.generate_dataset_reports import run_full_report_generation
    run_full_report_generation()


if __name__ == "__main__":
    process_widar_dataset()
    process_ntufi_dataset()
    generate_all_reports()
