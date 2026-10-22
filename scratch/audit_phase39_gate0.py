import sys
import json
from pathlib import Path
from collections import Counter

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "backend"))
sys.path.insert(0, str(BASE_DIR))

from app.services.split_generator import ParticipantIndependentSplitGenerator

def audit_gate0():
    print("=== Phase 39 Gate 0 Audit ===")
    manifest_path = BASE_DIR / "data" / "real_csi_dataset" / "dataset_manifest.json"
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
        
    split_gen = ParticipantIndependentSplitGenerator(manifest)
    res = split_gen.generate_strict_cross_room_split()
    
    sessions = res["sessions"]
    summary = res["splits_summary"]
    
    print("\nSummary:")
    for k, v in summary.items():
        if k != "windows_by_activity":
            print(f"  {k}: {v}")
            
    print("\nWindows by activity from splits_summary:")
    for split_name, act_dict in summary["windows_by_activity"].items():
        print(f"  Split '{split_name}': {act_dict}")

    by_split = {"train": [], "val": [], "test": [], "excluded": []}
    for s in sessions:
        by_split[s["split"]].append(s)
        
    print("\nDetailed Per-class session counts and window counts:")
    for split_name, s_list in by_split.items():
        sess_counter = Counter(s["activity_label"] for s in s_list)
        win_counter = Counter()
        for s in s_list:
            win_counter[s["activity_label"]] += s["packet_count"] // 50
            
        print(f"\n--- Split: {split_name} (Total sessions: {len(s_list)}, Total windows: {sum(win_counter.values())}) ---")
        for act in sorted(sess_counter.keys() | win_counter.keys()):
            print(f"  {act:12s}: {sess_counter[act]:2d} sessions, {win_counter[act]:2d} windows")

    print("\nTest sessions:")
    for s in by_split["test"]:
        wins = s["packet_count"] // 50
        print(f"  session_id={s['session_id']}, act={s['activity_label']}, part={s['participant_id']}, room={s['room']}, packets={s['packet_count']}, windows={wins}")

    print("\nVal sessions:")
    for s in by_split["val"]:
        wins = s["packet_count"] // 50
        print(f"  session_id={s['session_id']}, act={s['activity_label']}, part={s['participant_id']}, room={s['room']}, packets={s['packet_count']}, windows={wins}")

if __name__ == "__main__":
    audit_gate0()
