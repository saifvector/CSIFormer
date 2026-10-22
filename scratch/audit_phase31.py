import json, glob, os, hashlib, sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / 'backend'))

from backend.app.services.split_generator import ParticipantIndependentSplitGenerator

def run_audit():
    # 1. Checkpoint verification
    p13_md5 = hashlib.md5(open('models/csiformer_phase13_best.pth', 'rb').read()).hexdigest()
    p15_md5 = hashlib.md5(open('models/csiformer_phase15_adapted.pth', 'rb').read()).hexdigest()
    print("=== CHECKPOINT VERIFICATION ===")
    print(f"p13 MD5: {p13_md5} (Match: {p13_md5 == '383b4d98c08f8970b0443738f170ec01'})")
    print(f"p15 MD5: {p15_md5} (Match: {p15_md5 == 'ab3d97a04d78edf75d807178772bc828'})")

    # 2. Manifest and disk reconciliation
    manifest_path = 'data/real_csi_dataset/dataset_manifest.json'
    with open(manifest_path, 'r', encoding='utf-8') as f:
        manifest = json.load(f)

    sessions = manifest.get('sessions', [])
    print("\n=== DATASET INVENTORY ===")
    print(f"Total indexed sessions: {len(sessions)}")
    total_frames = sum(s.get('packet_count', 0) for s in sessions)
    print(f"Total frames (packet_count): {total_frames}")

    csv_files = glob.glob('data/real_csi_dataset/*.csv')
    json_files = glob.glob('data/real_csi_dataset/*.json')
    session_jsons = [f for f in json_files if not f.endswith('manifest.json') and 'manifest' not in os.path.basename(f)]

    print(f"Total CSVs on disk: {len(csv_files)}")
    print(f"Total Session JSONs on disk: {len(session_jsons)}")

    indexed_csvs = {s['csv_file'] for s in sessions}
    disk_csvs = {os.path.basename(p) for p in csv_files}
    unindexed_csvs = disk_csvs - indexed_csvs
    print(f"Unindexed CSVs ({len(unindexed_csvs)}): {sorted(unindexed_csvs)}")

    indexed_jsons = {s['json_file'] for s in sessions}
    disk_jsons = {os.path.basename(p) for p in session_jsons}
    unindexed_jsons = disk_jsons - indexed_jsons
    print(f"Unindexed JSONs ({len(unindexed_jsons)}): {sorted(unindexed_jsons)}")

    # Session ID and Event ID uniqueness
    session_ids = [s['session_id'] for s in sessions]
    event_ids = [s.get('event_id') or s['session_id'] for s in sessions]
    print(f"Unique session IDs: {len(set(session_ids))} / {len(sessions)}")
    print(f"Unique event IDs: {len(set(event_ids))} / {len(sessions)}")

    # 3. Comprehensive Breakdown
    matrix = {}
    raw_5_frames = 0
    derived_56_frames = 0
    total_windows = 0

    for s in sessions:
        r = s.get('room', 'Unknown')
        p = s.get('participant_id', 'Unknown')
        d = float(s.get('tx_rx_distance_m', 0.0))
        a = s.get('activity_label', 'Unknown')
        pkts = s.get('packet_count', 0)
        wins = pkts // 50
        total_windows += wins
        
        key = (r, p, d, a)
        if key not in matrix:
            matrix[key] = {'sessions': 0, 'frames': 0, 'windows': 0}
        matrix[key]['sessions'] += 1
        matrix[key]['frames'] += pkts
        matrix[key]['windows'] += wins

        # Check raw vs derived subcarriers
        jpath = os.path.join('data/real_csi_dataset', s['json_file'])
        with open(jpath, 'r', encoding='utf-8') as jf:
            data = json.load(jf)
        frames = data.get('frames', [])
        for fr in frames:
            if 'raw_amplitudes' in fr and len(fr['raw_amplitudes']) == 5:
                raw_5_frames += 1
            if ('amplitudes' in fr and len(fr['amplitudes']) == 56) or ('csi_matrix' in fr and len(fr['csi_matrix']) == 56):
                derived_56_frames += 1

    print(f"Total windows calculated: {total_windows}")
    print(f"Frames with raw 5 subcarriers: {raw_5_frames}")
    print(f"Frames with derived 56 channels: {derived_56_frames}")

    # Rooms summary
    room_p = {}
    for (r, p, d, a), vals in matrix.items():
        room_p.setdefault(r, set()).add(p)
    print("\n=== PARTICIPANTS PER ROOM ===")
    for r, p_set in sorted(room_p.items()):
        print(f"  {r}: {sorted(p_set)}")

    # Table of room x participant x distance x activity
    print("\n=== DETAILED COVERAGE MATRIX ===")
    print(f"{'Room':<18} | {'Participant':<15} | {'Dist(m)':<7} | {'Activity':<10} | {'Sessions':<8} | {'Frames':<8} | {'Windows':<8}")
    print("-" * 88)
    for (r, p, d, a), vals in sorted(matrix.items()):
        print(f"{r:<18} | {p:<15} | {d:<7.1f} | {a:<10} | {vals['sessions']:<8} | {vals['frames']:<8} | {vals['windows']:<8}")

    # 4. Split generator audit
    print("\n=== SPLIT GENERATOR AUDIT ===")
    gen = ParticipantIndependentSplitGenerator(Path(manifest_path))
    summary = gen.get_participant_summary()
    for p, psum in sorted(summary.items()):
        print(f"Participant {p}: {psum['session_count']} sessions, {psum['total_windows']} windows, activities={psum['activity_windows']}")

    split = gen.generate_loso_split(test_participant='Participant_02', val_participant='Participant_05', strict_coverage=False)
    ssum = split['splits_summary']
    print("\nSplit Windows:")
    print(f"  Train windows: {ssum['train_windows']} (Participants: {ssum['train_participants']})")
    print(f"  Val windows:   {ssum['val_windows']} (Participants: {ssum['val_participants']})")
    print(f"  Test windows:  {ssum['test_windows']} (Participants: {ssum['test_participants']})")
    print(f"  Sum of split windows: {ssum['train_windows'] + ssum['val_windows'] + ssum['test_windows']}")

    # What rooms are in Train, Val, Test?
    train_sessions = [s for s in sessions if s['participant_id'] in ssum['train_participants']]
    val_sessions = [s for s in sessions if s['participant_id'] in ssum['val_participants']]
    test_sessions = [s for s in sessions if s['participant_id'] in ssum['test_participants']]

    train_rooms = {s.get('room') for s in train_sessions}
    val_rooms = {s.get('room') for s in val_sessions}
    test_rooms = {s.get('room') for s in test_sessions}

    print(f"\nRooms in Train split: {sorted(train_rooms)}")
    print(f"Rooms in Val split:   {sorted(val_rooms)}")
    print(f"Rooms in Test split:  {sorted(test_rooms)}")

    # Office_Room2 breakdown
    office_sessions = [s for s in sessions if s.get('room') == 'Office_Room2']
    print(f"\nOffice_Room2 sessions ({len(office_sessions)}):")
    for s in office_sessions:
        print(f"  {s['session_id']}: participant={s['participant_id']}, activity={s['activity_label']}, dist={s['tx_rx_distance_m']}m, split={s['split']}")

if __name__ == '__main__':
    run_audit()
