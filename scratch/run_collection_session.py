"""
CSIFormer Phase 17 — Interactive/Automated CSI Collection Session CLI.

Usage Examples:
  # 1. Verify hardware connection and active CSI packet stream:
  py -3.11 scratch/run_collection_session.py --verify

  # 2. Record a 4-second walking trial:
  py -3.11 scratch/run_collection_session.py --activity walk --participant Participant_03 --duration 4.0 --confirm

  # 3. Record a safe, supervised fall trial:
  py -3.11 scratch/run_collection_session.py --activity fall --participant Participant_03 --duration 4.0 --confirm --notes "Padded landing mat forward drop"
"""

import sys
import time
import argparse
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))
sys.path.append(str(BASE_DIR / "backend"))

from app.services.collection_workflow import CollectionWorkflowManager, VALID_LABELS

def main():
    parser = argparse.ArgumentParser(description="CSIFormer Phase 17 Standardized Real-Data Collection")
    parser.add_argument("--port", default="COM5", help="Serial port of ESP32-S3 (default COM5)")
    parser.add_argument("--verify", action="store_true", help="Verify hardware connection and stream only")
    parser.add_argument("--activity", choices=list(VALID_LABELS.keys()), default="walk", help="Activity label")
    parser.add_argument("--participant", default="Participant_03", help="Pseudonymized participant ID")
    parser.add_argument("--duration", type=float, default=4.0, help="Duration in seconds (default 4.0)")
    parser.add_argument("--room", default="Laboratory", help="Room name or type")
    parser.add_argument("--distance", type=float, default=2.5, help="Tx-Rx distance in meters")
    parser.add_argument("--orientation", default="LOS_Facing_TxRx", help="Orientation relative to Tx-Rx baseline")
    parser.add_argument("--split", choices=["train", "val", "test"], default="train", help="Target split")
    parser.add_argument("--confirm", action="store_true", help="Confirm ground truth activity immediately")
    parser.add_argument("--notes", default="", help="Observational notes (e.g. mat setup)")

    args = parser.parse_args()

    manager = CollectionWorkflowManager(port=args.port)

    if args.verify:
        print("=" * 80)
        print("HARDWARE VERIFICATION CHECK")
        print("=" * 80)
        res = manager.verify_hardware_stream()
        print(f"Status:             {res['status'].upper()}")
        print(f"Port:               {res['port']}")
        print(f"Connected:          {res['connected']}")
        print(f"Packets in 1.5s:    {res.get('packets_received_during_test', 0)}")
        print(f"Sampling Rate:      {res.get('packet_rate_hz', 0.0):.1f} Hz")
        print(f"Mean RSSI:          {res.get('mean_rssi', -99.0):.1f} dBm")
        print("=" * 80)
        return

    print("=" * 80)
    print("PHASE 17 — PHYSICAL CSI COLLECTION SESSION")
    print("=" * 80)
    print(f"Activity:       {args.activity.upper()} ({VALID_LABELS[args.activity]['name']})")
    print(f"Participant:    {args.participant}")
    print(f"Duration:       {args.duration:.1f} seconds")
    print(f"Room / Setup:   {args.room} | Distance: {args.distance}m | Orientation: {args.orientation}")
    if args.activity == "fall":
        print("\n[SAFETY MANDATE] Ensure a minimum 4-inch padded gym mat is in place.")
        print("[SAFETY MANDATE] A spotter must be present. Never fall onto hard floors.\n")

    print("Starting session in 1.0s...")
    time.sleep(1.0)

    try:
        rec_start = manager.start_session(
            participant_id=args.participant,
            activity_label=args.activity,
            room_type=args.room,
            tx_rx_distance_m=args.distance,
            orientation=args.orientation,
            duration_seconds=args.duration,
            notes=args.notes
        )
        print(f"Recording Active: Session ID = {rec_start['session_id']}")

        # Wait for duration
        t0 = time.time()
        while time.time() - t0 < args.duration:
            elapsed = time.time() - t0
            print(f"  Recording... {elapsed:.1f}s / {args.duration:.1f}s", end="\r")
            time.sleep(0.1)
        print()

    finally:
        stop_res = manager.stop_session()
        print(f"Recording Finished. Frames Captured: {stop_res.get('frame_count', 0)}")
        print(f"Saved JSON: {stop_res.get('json_path')}")

    # Finalize
    confirmed = args.confirm
    if not confirmed:
        resp = input(f"Confirm ground-truth '{args.activity}' for this trial? (y/n): ").strip().lower()
        confirmed = (resp == "y")

    fin_res = manager.finalize_and_index_session(confirmed=confirmed, split=args.split, notes=args.notes)
    print(f"Session Finalized. Activity: {fin_res['activity_label']} | Manifest Updated: {fin_res['manifest_updated']}")
    print("=" * 80)

if __name__ == "__main__":
    main()
