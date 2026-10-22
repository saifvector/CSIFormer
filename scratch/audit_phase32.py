import sys
import json
import hashlib
from pathlib import Path

base_dir = Path(".").resolve()
sys.path.insert(0, str(base_dir))
sys.path.insert(0, str(base_dir / "backend"))

import numpy as np
from backend.app.services.csi_preprocessor import CSIPreprocessor
from backend.app.services.split_generator import ParticipantIndependentSplitGenerator
from backend.app.services.session_validator import DatasetIntegrityValidator, compute_session_sampling_rate

base_dir = Path(".").resolve()
dataset_dir = base_dir / "data" / "real_csi_dataset"
manifest_path = dataset_dir / "dataset_manifest.json"
models_dir = base_dir / "models"

# Checkpoints
p13 = hashlib.md5((models_dir / "csiformer_phase13_best.pth").read_bytes()).hexdigest()
p15 = hashlib.md5((models_dir / "csiformer_phase15_adapted.pth").read_bytes()).hexdigest()
print(f"P13 MD5: {p13} (matches: {p13 == '383b4d98c08f8970b0443738f170ec01'})")
print(f"P15 MD5: {p15} (matches: {p15 == 'ab3d97a04d78edf75d807178772bc828'})")

# Task 1: Reconcile Physical Dataset
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
sessions = manifest["sessions"]
print(f"Total sessions in manifest: {len(sessions)}")

# Disk reconciliation
all_csv_on_disk = sorted([f.name for f in dataset_dir.glob("*.csv")])
all_json_on_disk = sorted([f.name for f in dataset_dir.glob("*.json") if f.name != "dataset_manifest.json" and f.name != "dataset_manifest_p17_loso.json"])

manifest_csvs = sorted([s["csv_file"] for s in sessions])
manifest_jsons = sorted([s["json_file"] for s in sessions])

csv_manifest_to_disk_missing = [c for c in manifest_csvs if c not in all_csv_on_disk]
csv_disk_to_manifest_unindexed = [c for c in all_csv_on_disk if c not in manifest_csvs]
json_manifest_to_disk_missing = [j for j in manifest_jsons if j not in all_json_on_disk]
json_disk_to_manifest_unindexed = [j for j in all_json_on_disk if j not in manifest_jsons]

print(f"CSV files on disk: {len(all_csv_on_disk)}")
print(f"JSON files on disk (excluding manifests): {len(all_json_on_disk)}")
print(f"CSV manifest->disk missing: {csv_manifest_to_disk_missing}")
print(f"CSV disk->manifest unindexed: {csv_disk_to_manifest_unindexed}")
print(f"JSON manifest->disk missing: {json_manifest_to_disk_missing}")
print(f"JSON disk->manifest unindexed: {json_disk_to_manifest_unindexed}")

# Frame parity & windowing
total_packets = 0
total_windows_floor = 0
total_windows_segmented = 0
min_pkts = 999999
max_pkts = 0
sessions_with_raw_5 = 0
frames_with_raw_5 = 0
sessions_with_56 = 0
frames_with_56 = 0
sample_rates = []

for s in sessions:
    sid = s["session_id"]
    pkts = s["packet_count"]
    fc = s.get("frame_count", pkts)
    assert pkts == fc, f"Session {sid}: packet_count {pkts} != frame_count {fc}"
    
    total_packets += pkts
    wins_floor = pkts // 50
    total_windows_floor += wins_floor
    
    # Run through CSIPreprocessor.segment_windows
    dummy = np.zeros((pkts, 56), dtype=np.float32)
    wins_seg = CSIPreprocessor.segment_windows(dummy, window_size=50, stride=50)
    assert len(wins_seg) == wins_floor, f"Session {sid}: {len(wins_seg)} != {wins_floor}"
    total_windows_segmented += len(wins_seg)
    
    if pkts < min_pkts: min_pkts = pkts
    if pkts > max_pkts: max_pkts = pkts
    
    # Check JSON file content on disk
    jdata = json.loads((dataset_dir / s["json_file"]).read_text(encoding="utf-8"))
    frames = jdata.get("frames", [])
    assert len(frames) == pkts, f"Session {sid}: JSON frames {len(frames)} != pkts {pkts}"
    
    # Check CSV row count
    c_lines = (dataset_dir / s["csv_file"]).read_text(encoding="utf-8").strip().splitlines()
    header = c_lines[0].split(",")
    csv_rows = len(c_lines) - 1
    assert csv_rows == pkts, f"Session {sid}: CSV rows {csv_rows} != pkts {pkts}"
    
    # Sampling rate from timestamps and metadata
    timestamps = [f.get("timestamp") for f in frames if "timestamp" in f]
    meta = jdata.get("metadata", {})
    rate_metrics = compute_session_sampling_rate(timestamps, wall_duration_s=meta.get("duration_seconds"))
    if rate_metrics.get("valid"):
        sample_rates.append(rate_metrics["empirical_sampling_rate_hz"])
    elif "empirical_sampling_rate_hz" in meta:
        sample_rates.append(meta["empirical_sampling_rate_hz"])
    elif "sample_rate_hz" in s:
        sample_rates.append(s["sample_rate_hz"])

    # Raw vs derived channels
    has_raw = False
    if "raw_subcarriers" in s or "subcarrier_raw" in s or s.get("preserves_raw_subcarriers"):
        has_raw = True
    elif len(frames) > 0:
        first_frame = frames[0]
        if "raw_csi" in first_frame or "raw_complex" in first_frame or "subcarrier_pairs" in first_frame or "subcarriers_raw" in first_frame or "raw_iq" in first_frame or "raw_subcarrier_pairs" in first_frame:
            has_raw = True
        elif "raw_subcarriers" in meta or meta.get("preserves_raw_subcarriers"):
            has_raw = True

    if has_raw:
        sessions_with_raw_5 += 1
        frames_with_raw_5 += pkts

    # Check 56 channels
    first_frame = frames[0] if len(frames) > 0 else {}
    if len(header) >= 56 or "csi_features" in first_frame or len(first_frame.get("csi_amplitude", [])) == 56 or len(first_frame.get("csi_data", [])) == 56 or "csi_amplitude" in first_frame:
        sessions_with_56 += 1
        frames_with_56 += pkts

print(f"Total physical frames: {total_packets}")
print(f"Total windows (floor division): {total_windows_floor}")
print(f"Total windows (segment_windows): {total_windows_segmented}")
print(f"Packet range per session: {min_pkts} to {max_pkts}")
print(f"Sampling rates: count={len(sample_rates)}, min={min(sample_rates):.2f}, max={max(sample_rates):.2f}, mean={np.mean(sample_rates):.2f}")
print(f"Sessions with raw 5 subcarriers: {sessions_with_raw_5}, frames: {frames_with_raw_5}")
print(f"Sessions with 56 channels: {sessions_with_56}, frames: {frames_with_56}")

# Check rooms & participants
room_counts = {}
for s in sessions:
    r = s.get("room")
    p = s.get("participant_id")
    a = s.get("activity_label")
    d = s.get("distance_m")
    room_counts.setdefault(r, {}).setdefault(p, []).append((d, a))

print("\nRoom -> Participant session distribution:")
for r, pdict in sorted(room_counts.items()):
    print(f"Room: {r}")
    for p, sessions_list in sorted(pdict.items()):
        print(f"  {p}: {len(sessions_list)} sessions (distances: {sorted(list(set(d for d, _ in sessions_list)))})")
