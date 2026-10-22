import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
MANIFEST_PATH = BASE_DIR / "data" / "real_csi_dataset" / "dataset_manifest.json"

with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
    manifest = json.load(f)

sessions = manifest["sessions"]

split_counts = {}
for s in sessions:
    sp = s.get("split", "missing")
    split_counts[sp] = split_counts.get(sp, 0) + 1

print("Persisted split field counts in dataset_manifest.json:")
for sp, cnt in sorted(split_counts.items()):
    print(f"  {sp}: {cnt}")

print("\nSplits summary block in manifest:")
print(json.dumps(manifest.get("splits_summary", {}), indent=2))

# Check Office_Room2 sessions
office_sessions = [s for s in sessions if s.get("room") == "Office_Room2"]
print(f"\nTotal Office_Room2 sessions: {len(office_sessions)}")
for s in office_sessions:
    print(f"  {s['participant_id']} | {s['activity_label']} | split in manifest: '{s.get('split')}' | session_id: {s['session_id']}")

# Check per-participant room and split breakdown
print("\nParticipant breakdown:")
for p in sorted(list(set(s["participant_id"] for s in sessions))):
    p_sessions = [s for s in sessions if s["participant_id"] == p]
    rooms = sorted(list(set(s.get("room", "Unknown") for s in p_sessions)))
    splits = {s.get("split"): sum(1 for x in p_sessions if x.get("split") == s.get("split")) for s in p_sessions}
    total_wins = sum(s["packet_count"] // 50 for s in p_sessions)
    print(f"  {p}: {len(p_sessions)} sessions, {total_wins} windows, rooms={rooms}, splits={splits}")
