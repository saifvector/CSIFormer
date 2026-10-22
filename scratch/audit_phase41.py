import json
from pathlib import Path

manifest_path = Path("data/real_csi_dataset/dataset_manifest.json")
with open(manifest_path, "r") as f:
    manifest = json.load(f)

sessions = manifest["sessions"]
print(f"Total sessions in manifest: {len(sessions)}")

raw_sc_dist = {}
static_sit_prov = []
phase_counts = {}
rooms = set()
participants = set()
sampling_rates = []
packet_losses = []

for s in sessions:
    sid = s["session_id"]
    jfile = s.get("json_file", f"{sid}.json")
    jpath = Path("data/real_csi_dataset") / jfile
    with open(jpath, "r", encoding="utf-8") as f:
        data = json.load(f)
    meta = data.get("metadata", {})
    frames = data.get("frames", [])
    phase = sid.split("_")[0]
    phase_counts[phase] = phase_counts.get(phase, 0) + 1
    rooms.add(meta.get("room_type", "Unknown"))
    participants.add(meta.get("participant_id", "Unknown"))
    
    first_frame = frames[0] if frames else {}
    has_raw = "raw_amplitudes" in first_frame
    raw_len = len(first_frame["raw_amplitudes"]) if has_raw else "None"
    raw_sc_dist[raw_len] = raw_sc_dist.get(raw_len, 0) + 1
    
    sr = meta.get("mean_sampling_rate_hz")
    if sr is not None:
        sampling_rates.append(sr)
    
    pkts_lost = meta.get("packets_lost", 0)
    loss_rate = meta.get("loss_rate", 0.0)
    packet_losses.append((pkts_lost, loss_rate))
    
    act = meta.get("ground_truth_activity") or s.get("activity_label")
    if act in ("static", "sit"):
        static_sit_prov.append({
            "session_id": sid,
            "phase": phase,
            "act": act,
            "pid": meta.get("participant_id"),
            "room": meta.get("room_type"),
            "frames": len(frames),
            "retained_windows": len(frames) // 50,
            "remainder_frames": len(frames) % 50,
            "has_raw": has_raw,
            "sampling_rate": sr
        })

print(f"Phase breakdown: {phase_counts}")
print(f"Raw subcarrier distribution: {raw_sc_dist}")
print(f"Rooms represented: {sorted(list(rooms))}")
print(f"Participants represented: {sorted(list(participants))}")
print(f"Mean sampling rate across all sessions: {sum(sampling_rates)/len(sampling_rates):.2f} Hz (min: {min(sampling_rates):.2f}, max: {max(sampling_rates):.2f})")
print(f"Total sessions with packets_lost > 0: {sum(1 for p, l in packet_losses if p > 0)}")
print(f"\nStatic and Sit Sessions count: {len(static_sit_prov)}")
for item in static_sit_prov:
    print(f"  {item['session_id']} | {item['act']} | {item['pid']} | {item['room']} | frames={item['frames']} (win={item['retained_windows']}, rem={item['remainder_frames']}) | raw={item['has_raw']} | sr={item['sampling_rate']}")
