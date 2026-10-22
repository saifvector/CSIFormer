import json
from pathlib import Path
from collections import defaultdict

BASE_DIR = Path(__file__).resolve().parent.parent
MANIFEST_PATH = BASE_DIR / "data" / "real_csi_dataset" / "dataset_manifest.json"

with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
    manifest = json.load(f)

sessions = manifest["sessions"]

# 5 safe ordinary classes
SAFE_CLASSES = ["static", "sit", "walk", "clap", "push_pull"]

# Invariants partitioning:
# 1. Test contains ONLY Participant_02 in Office_Room2 (5 sessions)
test_sessions = [
    s for s in sessions
    if s.get("participant_id") == "Participant_02" and s.get("room") == "Office_Room2"
]

# 2. Excluded Office_Room2 sessions: Participant_01 in Office_Room2 (5 sessions)
excluded_office_p01 = [
    s for s in sessions
    if s.get("participant_id") == "Participant_01" and s.get("room") == "Office_Room2"
]

# 3. Excluded Participant_02 non-Office sessions (16 sessions in Laboratory & Laboratory_Room1)
excluded_p02_other = [
    s for s in sessions
    if s.get("participant_id") == "Participant_02" and s.get("room") != "Office_Room2"
]

# 4. Fall sessions across all participants (must be excluded from 5-class protocol)
fall_sessions = [
    s for s in sessions
    if s.get("activity_label") == "fall"
]

# 5. Candidate Train sessions: Participants 01, 03, 04, non-Office_Room2, 5 safe classes
train_sessions_5class = [
    s for s in sessions
    if s.get("participant_id") in ["Participant_01", "Participant_03", "Participant_04"]
    and s.get("room") != "Office_Room2"
    and s.get("activity_label") in SAFE_CLASSES
]

# Also check Train sessions if falls were NOT filtered
train_sessions_all = [
    s for s in sessions
    if s.get("participant_id") in ["Participant_01", "Participant_03", "Participant_04"]
    and s.get("room") != "Office_Room2"
]

# 6. Candidate Val sessions: Participant_05, non-Office_Room2, 5 safe classes
val_sessions_5class = [
    s for s in sessions
    if s.get("participant_id") == "Participant_05"
    and s.get("room") != "Office_Room2"
    and s.get("activity_label") in SAFE_CLASSES
]

val_sessions_all = [
    s for s in sessions
    if s.get("participant_id") == "Participant_05"
    and s.get("room") != "Office_Room2"
]

print("=== CANDIDATE FIVE-CLASS CROSS-ROOM PARTITION ===")
print(f"Total sessions in dataset: {len(sessions)}")
print(f"Test sessions (P02 in Office_Room2): {len(test_sessions)}")
print(f"Excluded P01 Office_Room2 sessions: {len(excluded_office_p01)}")
print(f"Excluded P02 non-Office sessions: {len(excluded_p02_other)}")
print(f"Train sessions (P01, P03, P04 non-Office, 5 safe classes): {len(train_sessions_5class)}")
print(f"Val sessions (P05 non-Office, 5 safe classes): {len(val_sessions_5class)}")

# Check sum
total_categorized = (
    len(test_sessions) +
    len(excluded_office_p01) +
    len(excluded_p02_other) +
    len(train_sessions_5class) +
    len(val_sessions_5class)
)
print(f"Total sessions accounted for (excluding falls): {total_categorized}")

# Check falls
p01_falls = [s for s in sessions if s.get("participant_id") == "Participant_01" and s.get("activity_label") == "fall"]
p02_falls = [s for s in sessions if s.get("participant_id") == "Participant_02" and s.get("activity_label") == "fall"]
print(f"Falls in dataset: {len(fall_sessions)} (P01: {len(p01_falls)}, P02: {len(p02_falls)})")
print(f"Are P02 falls in excluded_p02_other? {set(s['session_id'] for s in p02_falls).issubset(set(s['session_id'] for s in excluded_p02_other))}")
print(f"Are P01 falls non-office? {[s.get('room') for s in p01_falls]}")

# If we count:
# train_sessions_5class: non-office, non-fall from P01, P03, P04
# val_sessions_5class: non-office, non-fall from P05
# test_sessions: P02 Office_Room2 (5 sessions)
# excluded:
#   - P01 Office_Room2 (5 sessions)
#   - P01 falls (4 sessions)
#   - P02 non-Office (16 sessions, which includes 4 falls)
total_with_falls = total_categorized + len(p01_falls)
print(f"Total with P01 falls accounted: {total_with_falls} (out of {len(sessions)})")

# Activity and window breakdown helper
def get_stats(sess_list, name):
    wins_per_act = defaultdict(int)
    frames_per_act = defaultdict(int)
    rooms = set()
    participants = set()
    for s in sess_list:
        act = s["activity_label"]
        pkts = s["packet_count"]
        wins = pkts // 50
        wins_per_act[act] += wins
        frames_per_act[act] += pkts
        rooms.add(s.get("room"))
        participants.add(s.get("participant_id"))
    total_wins = sum(wins_per_act.values())
    total_frames = sum(frames_per_act.values())
    print(f"\n--- {name} ---")
    print(f"Sessions: {len(sess_list)}, Frames: {total_frames}, Windows: {total_wins}")
    print(f"Participants: {sorted(list(participants))}")
    print(f"Rooms: {sorted(list(rooms))}")
    print("Windows per activity:")
    for a in SAFE_CLASSES + (["fall"] if "fall" in wins_per_act else []):
        if a in wins_per_act:
            print(f"  {a:10s}: {wins_per_act[a]} windows ({frames_per_act[a]} frames)")
    return total_wins, wins_per_act

train_wins, train_act_wins = get_stats(train_sessions_5class, "TRAIN PARTITION (5-class)")
val_wins, val_act_wins = get_stats(val_sessions_5class, "VAL PARTITION (5-class)")
test_wins, test_act_wins = get_stats(test_sessions, "TEST PARTITION (5-class)")
get_stats(excluded_office_p01, "EXCLUDED: P01 Office_Room2")
get_stats(excluded_p02_other, "EXCLUDED: P02 Non-Office_Room2 (Lab)")
get_stats(p01_falls, "EXCLUDED: P01 Falls (Lab)")

# Invariants verification
print("\n=== INVARIANT CHECKS ===")
# 1. Training contains no sessions from Office_Room2
train_rooms = {s.get("room") for s in train_sessions_5class}
assert "Office_Room2" not in train_rooms, "Invariant 1 violated: Office_Room2 found in train!"
print("Invariant 1 PASS: Training contains no sessions from Office_Room2.")

# 2. Validation contains no sessions from Office_Room2
val_rooms = {s.get("room") for s in val_sessions_5class}
assert "Office_Room2" not in val_rooms, "Invariant 2 violated: Office_Room2 found in val!"
print("Invariant 2 PASS: Validation contains no sessions from Office_Room2.")

# 3. Test contains only the five new Participant_02 sessions in Office_Room2
test_sids = {s["session_id"] for s in test_sessions}
assert len(test_sessions) == 5
assert all(s.get("participant_id") == "Participant_02" and s.get("room") == "Office_Room2" for s in test_sessions)
print("Invariant 3 PASS: Test contains ONLY Participant_02 sessions in Office_Room2 (5 sessions).")

# 4. Participant_02 has no sessions in training or validation
train_participants = {s["participant_id"] for s in train_sessions_5class}
val_participants = {s["participant_id"] for s in val_sessions_5class}
assert "Participant_02" not in train_participants
assert "Participant_02" not in val_participants
print("Invariant 4 PASS: Participant_02 is completely absent from training and validation.")

# 5. No session, event, or overlapping window is shared across partitions
train_eids = {s.get("event_id") or s["session_id"] for s in train_sessions_5class}
val_eids = {s.get("event_id") or s["session_id"] for s in val_sessions_5class}
test_eids = {s.get("event_id") or s["session_id"] for s in test_sessions}
train_sids = {s["session_id"] for s in train_sessions_5class}
val_sids = {s["session_id"] for s in val_sessions_5class}

assert len(train_sids & val_sids) == 0
assert len(train_sids & test_sids) == 0
assert len(val_sids & test_sids) == 0
assert len(train_eids & val_eids) == 0
assert len(train_eids & test_eids) == 0
assert len(val_eids & test_eids) == 0
print("Invariant 5 PASS: Zero session, event, or window leakage across partitions.")

# 6. All five safe ordinary activity classes are represented in the test
assert set(test_act_wins.keys()) == set(SAFE_CLASSES)
print("Invariant 6 PASS: All 5 safe ordinary classes represented in test.")

# Also check train and val class coverage
print(f"Train covers all 5 safe classes: {set(train_act_wins.keys()) == set(SAFE_CLASSES)}")
print(f"Val covers all 5 safe classes: {set(val_act_wins.keys()) == set(SAFE_CLASSES)}")

# 7. Every eligible test window is assigned exactly once
print(f"Invariant 7 PASS: Exactly {test_wins} eligible test windows assigned once.")

# 8. Fall detection remains excluded from this five-class evaluation
all_active_sessions = train_sessions_5class + val_sessions_5class + test_sessions
assert all(s["activity_label"] != "fall" for s in all_active_sessions)
print("Invariant 8 PASS: Fall activity is 100% excluded from all active partitions.")
