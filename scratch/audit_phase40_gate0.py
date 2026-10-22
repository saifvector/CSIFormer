import sys
import json
from pathlib import Path
from collections import Counter

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "backend"))
sys.path.insert(0, str(BASE_DIR))

from app.services.split_generator import ParticipantIndependentSplitGenerator

def audit_gate0():
    print("=== Phase 40 Gate 0 Audit ===")
    manifest_path = BASE_DIR / "data" / "real_csi_dataset" / "dataset_manifest.json"
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
        
    print(f"Total sessions in manifest: {len(manifest['sessions'])}")
    
    # 1. Inspect Fall sessions in manifest
    falls = [s for s in manifest["sessions"] if s.get("activity_label") == "fall"]
    print(f"\n--- Fall Sessions in Manifest ({len(falls)} sessions) ---")
    total_fall_pkts = 0
    total_fall_wins_floor = 0
    for s in falls:
        pkt = s["packet_count"]
        total_fall_pkts += pkt
        wins = pkt // 50
        total_fall_wins_floor += wins
        rem = pkt % 50
        print(f"  {s['session_id']}: pkts={pkt}, wins(//50)={wins}, rem={rem}, split={s.get('split')}, part={s.get('participant_id')}, room={s.get('room')}")
    print(f"Total fall packets: {total_fall_pkts}")
    print(f"Total fall windows (floor division // 50): {total_fall_wins_floor}")
    
    # Check if there are other references to fall in splits_summary in the manifest itself
    if "splits_summary" in manifest:
        print("\nManifest's existing splits_summary:")
        print(json.dumps(manifest["splits_summary"], indent=2))

    # 2. Run generate_strict_cross_room_split()
    gen = ParticipantIndependentSplitGenerator(manifest)
    res = gen.generate_strict_cross_room_split()
    summary = res["splits_summary"]
    
    print("\n--- Strict Cross-Room Split Summary ---")
    for k, v in summary.items():
        if k not in ["windows_by_activity", "exclusion_reasons"]:
            print(f"  {k}: {v}")
            
    print("\nWindows by activity:")
    for split_name, act_dict in summary["windows_by_activity"].items():
        print(f"  {split_name}: {act_dict}")
        
    print("\nExclusion reasons:")
    for reason, count in summary["exclusion_reasons"].items():
        print(f"  {reason}: {count}")

    # 3. Check every partition's sessions, frames, windows, remainders
    by_split = {"train": [], "val": [], "test": [], "excluded": []}
    for s in res["sessions"]:
        by_split[s["split"]].append(s)
        
    print("\n--- Detailed Partition Accounting ---")
    for split_name, s_list in by_split.items():
        pkts = sum(s["packet_count"] for s in s_list)
        wins = sum(s["packet_count"] // 50 for s in s_list)
        rems = sum(s["packet_count"] % 50 for s in s_list)
        print(f"Partition: {split_name:8s} | Sessions: {len(s_list):2d} | Total Packets: {pkts:5d} | Windows: {wins:2d} | Dropped Remainder Frames: {rems:4d}")

if __name__ == "__main__":
    audit_gate0()
