import json
from pathlib import Path

dataset_dir = Path("data/real_csi_dataset")
all_json = sorted(list(dataset_dir.glob("*.json")))
print(f"Total JSON files on disk: {len(all_json)}")

manifest_path = dataset_dir / "dataset_manifest.json"
with open(manifest_path, "r", encoding="utf-8") as f:
    manifest = json.load(f)

sessions = manifest.get("sessions", [])
print(f"Total indexed sessions in manifest: {len(sessions)}")

manifest_files = set(s["json_file"] for s in sessions)
disk_files = set(p.name for p in all_json if p.name not in ["dataset_manifest.json", "dataset_manifest_p17_loso.json"])

unindexed = disk_files - manifest_files
print(f"Unindexed session files: {unindexed}")

tot_pkts = 0
tot_windows = 0
participants = set()
events = set()
rooms = set()
distances = set()
activities = {}

for s in sessions:
    p = dataset_dir / s["json_file"]
    with open(p, "r", encoding="utf-8") as jf:
        d = json.load(jf)
    actual_frames = len(d.get("frames", []))
    sid = s["session_id"]
    if actual_frames != s["packet_count"]:
        print(f"Mismatch in {sid}: manifest={s['packet_count']} vs disk={actual_frames}")
    tot_pkts += actual_frames
    wins = actual_frames // 50
    tot_windows += wins
    participants.add(s["participant_id"])
    events.add(s.get("event_id") or sid)
    rooms.add(s["room"])
    distances.add(s["tx_rx_distance_m"])
    act = s["activity_label"]
    activities[act] = activities.get(act, 0) + wins

print(f"Total verified packets across 23 sessions: {tot_pkts}")
print(f"Total verified windows (50 frames): {tot_windows}")
print(f"Distinct participants: {sorted(list(participants))}")
print(f"Distinct events: {len(events)}")
print(f"Distinct rooms: {sorted(list(rooms))}")
print(f"Distinct distances: {sorted(list(distances))}")
print(f"Activity window breakdown: {activities}")

for uf in unindexed:
    up = dataset_dir / uf
    with open(up, "r", encoding="utf-8") as f:
        ud = json.load(f)
    print(f"Unindexed file {uf}: frames={len(ud.get('frames', []))}, meta={ud.get('metadata')}")

# Now let's audit dataset_manifest_p17_loso.json
loso_manifest_path = dataset_dir / "dataset_manifest_p17_loso.json"
if loso_manifest_path.exists():
    with open(loso_manifest_path, "r", encoding="utf-8") as f:
        loso_m = json.load(f)
    print("\n--- LOSO Manifest Audit ---")
    print(f"Train participants: {loso_m.get('train_participants')}")
    print(f"Val participants: {loso_m.get('val_participants')}")
    print(f"Test participants: {loso_m.get('test_participants')}")
    summary = loso_m.get("splits_summary", {})
    print(f"Train windows: {summary.get('train_windows')}, sessions: {summary.get('train_sessions')}, events: {summary.get('train_events')}")
    print(f"Val windows: {summary.get('val_windows')}, sessions: {summary.get('val_sessions')}, events: {summary.get('val_events')}")
    print(f"Test windows: {summary.get('test_windows')}, sessions: {summary.get('test_sessions')}, events: {summary.get('test_events')}")
    print(f"Fall events: {summary.get('fall_events')}")
    print(f"Fall windows: {summary.get('fall_windows')}")
