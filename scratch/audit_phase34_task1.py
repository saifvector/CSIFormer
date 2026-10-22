import json
from pathlib import Path
import numpy as np
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = BASE_DIR / "backend"
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from backend.app.services.session_validator import DatasetIntegrityValidator, compute_session_sampling_rate
from backend.app.services.csi_preprocessor import CSIPreprocessor

DATASET_DIR = BASE_DIR / "data" / "real_csi_dataset"
MANIFEST_PATH = DATASET_DIR / "dataset_manifest.json"

with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
    manifest = json.load(f)

sessions = manifest["sessions"]
print(f"Total indexed sessions in manifest: {len(sessions)}")
print(f"Total packet_count sum: {sum(s['packet_count'] for s in sessions)}")

# Disk reconciliation
all_csv = {p.name for p in DATASET_DIR.glob("*.csv")}
all_json = {p.name for p in DATASET_DIR.glob("*.json") if "manifest" not in p.name}
indexed_csv = {s["csv_file"] for s in sessions}
indexed_json = {s["json_file"] for s in sessions}

print(f"Total CSV on disk: {len(all_csv)}")
print(f"Total JSON on disk: {len(all_json)}")
print(f"Manifest-to-disk CSV missing: {indexed_csv - all_csv}")
print(f"Manifest-to-disk JSON missing: {indexed_json - all_json}")
print(f"Disk unindexed CSV: {all_csv - indexed_csv}")
print(f"Disk unindexed JSON: {all_json - indexed_json}")

# Check Phase 33 target sessions
p02_office = [s for s in sessions if s.get("room") == "Office_Room2" and s.get("participant_id") == "Participant_02"]
print(f"\nParticipant_02 in Office_Room2 sessions: {len(p02_office)}")

p02_activities = set()
total_p02_frames = 0
total_p02_windows = 0

for s in p02_office:
    act = s["activity_label"]
    p02_activities.add(act)
    jpath = DATASET_DIR / s["json_file"]
    cpath = DATASET_DIR / s["csv_file"]
    assert jpath.exists(), f"Missing JSON: {jpath}"
    assert cpath.exists(), f"Missing CSV: {cpath}"
    
    with open(jpath, "r", encoding="utf-8") as jf:
        jdata = json.load(jf)
    
    frames = jdata.get("frames", [])
    pkts = len(frames)
    total_p02_frames += pkts
    wins = pkts // 50
    total_p02_windows += wins
    assert pkts == s["packet_count"], f"Frame count mismatch: {pkts} vs {s['packet_count']}"
    
    # CSV row check
    csv_lines = cpath.read_text(encoding="utf-8").strip().split("\n")
    assert len(csv_lines) - 1 == pkts, f"CSV rows mismatch: {len(csv_lines)-1} vs {pkts}"
    
    # Raw and derived
    assert len(frames[0].get("raw_amplitudes", [])) == 5
    assert len(frames[0].get("raw_phases", [])) == 5
    assert len(frames[0].get("amplitudes", [])) == 56
    assert len(frames[0].get("phases", [])) == 56
    
    # Timestamps monotonicity
    ts = [f["timestamp"] for f in frames if "timestamp" in f]
    assert len(ts) == pkts
    assert all(t2 > t1 for t1, t2 in zip(ts[:-1], ts[1:])), "Timestamps not strictly monotonic"
    
    # Rate stats
    rate_stats = compute_session_sampling_rate(ts, wall_duration_s=s["duration_seconds"])
    assert rate_stats["valid"] is True
    
    print(f"Verified {act}: pkts={pkts}, dur={s['duration_seconds']}s, rate={s['sampling_rate_hz']:.2f}Hz, emp_rate={rate_stats['empirical_sampling_rate_hz']:.2f}Hz, dist={s['tx_rx_distance_m']}m, split={s.get('split')}, status={s.get('confirmation_status')}")

print(f"\nP02 Office_Room2 activities: {sorted(list(p02_activities))}")
print(f"P02 Office_Room2 total frames: {total_p02_frames}")
print(f"P02 Office_Room2 total windows: {total_p02_windows}")

# Global window count verification using CSIPreprocessor.segment_windows
total_frames = 0
total_windows_floor = 0
total_windows_segmented = 0

for s in sessions:
    pkts = s["packet_count"]
    total_frames += pkts
    wins_floor = pkts // 50
    total_windows_floor += wins_floor
    dummy = np.zeros((pkts, 56), dtype=np.float32)
    windows = CSIPreprocessor.segment_windows(dummy, window_size=50, stride=50)
    assert len(windows) == wins_floor
    total_windows_segmented += len(windows)

print(f"\nGlobal total frames: {total_frames}")
print(f"Global total windows (floor): {total_windows_floor}")
print(f"Global total windows (segmented): {total_windows_segmented}")

# Run dataset validator
validator = DatasetIntegrityValidator(DATASET_DIR, MANIFEST_PATH)
val_res = validator.validate_dataset_manifest()
print(f"Dataset integrity validator: all_sessions_valid = {val_res['all_sessions_valid']}")
