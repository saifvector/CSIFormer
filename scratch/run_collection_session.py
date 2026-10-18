"""
CSIFormer Phase 18 — Interactive/Automated Physical CSI Collection Session CLI.

Standardized tool for operator-guided real-hardware data collection:
- Hardware link check and UDP stimulator verification.
- Enforces pseudonymized participant IDs (e.g. Participant_03).
- Event-level tracking with unique event_id to prevent window/event split leakage.
- Precise Tx/Rx geometric positioning.
- Post-trial ground-truth confirmation or rejection gate.
- Strict padded-mat fall safety warnings.

Usage Examples:
  # 1. Verify hardware connection and active CSI packet stream:
  py -3.11 scratch/run_collection_session.py --verify

  # 2. Record a 4-second walking trial:
  py -3.11 scratch/run_collection_session.py --activity walk --participant Participant_03 --duration 4.0 --confirm

  # 3. Record a safe, supervised fall trial on a certified 4-inch mat:
  py -3.11 scratch/run_collection_session.py --activity fall --participant Participant_03 --duration 4.0 --confirm --notes "Certified 4-inch mat forward breakfall"
"""

import sys
import time
import argparse
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))
sys.path.append(str(BASE_DIR / "backend"))

from app.services.collection_workflow import CollectionWorkflowManager, VALID_LABELS, DATASET_DIR
from app.services.session_validator import DatasetIntegrityValidator

def main():
    parser = argparse.ArgumentParser(description="CSIFormer Phase 20 Standardized Real-Data Collection")
    parser.add_argument("--port", default="COM5", help="Serial port of ESP32-S3 (default COM5)")
    parser.add_argument("--verify", action="store_true", help="Verify hardware connection and stream only")
    parser.add_argument("--validate", action="store_true", help="Validate existing dataset manifest and session files")
    parser.add_argument("--activity", choices=list(VALID_LABELS.keys()), default="walk", help="Activity label")
    parser.add_argument("--participant", default="Participant_03", help="Pseudonymized participant ID")
    parser.add_argument("--duration", type=float, default=4.0, help="Duration in seconds (default 4.0)")
    parser.add_argument("--room", default="Laboratory", help="Room name or type")
    parser.add_argument("--distance", type=float, default=2.5, help="Tx-Rx distance in meters")
    parser.add_argument("--tx-pos", default="Tx_Baseline_Origin", help="Transmitter physical position / coordinates")
    parser.add_argument("--rx-pos", default="Rx_Baseline_Node", help="Receiver physical position / coordinates")
    parser.add_argument("--orientation", default="LOS_Facing_TxRx", help="Orientation relative to Tx-Rx baseline")
    parser.add_argument("--event", default=None, help="Explicit event ID (default auto-generated)")
    parser.add_argument("--split", choices=["train", "val", "test"], default="train", help="Target split")
    parser.add_argument("--confirm", action="store_true", help="Confirm ground truth activity immediately")
    parser.add_argument("--notes", default="", help="Observational notes (e.g. mat setup)")

    args = parser.parse_args()

    if args.validate:
        print("=" * 80)
        print("DATASET INTEGRITY & VALIDATION CHECK (PHASE 20)")
        print("=" * 80)
        validator = DatasetIntegrityValidator(DATASET_DIR)
        res = validator.validate_dataset_manifest()
        print(f"Manifest Status:        {'VALID' if res['all_sessions_valid'] else 'INVALID'}")
        print(f"Total Sessions:         {res['total_sessions']}")
        print(f"Total Packets:          {res['total_packets']}")
        print(f"Total Windows (50 frames): {res['total_windows']}")
        print(f"Distinct Participants:  {res['distinct_participants']}")
        print(f"Distinct Events:        {res['distinct_events']}")
        print(f"Activity Windows:       {res['activity_windows']}")
        print("=" * 80)
        return

    manager = CollectionWorkflowManager(port=args.port)

    if args.verify:
        verify_dur = args.duration if args.duration != 4.0 else 12.0
        print("=" * 80)
        print("PHASE 21 — HARDWARE VERIFICATION & DIAGNOSTIC CHECK")
        print("=" * 80)
        print(f"Testing port {args.port} for {verify_dur:.1f}s...")
        res = manager.verify_hardware_stream(test_duration_s=verify_dur)
        print(f"Status:             {res['status'].upper()}")
        print(f"Diagnostic State:   {res.get('diagnostic_state', 'UNKNOWN')}")
        print(f"Port:               {res['port']} @ {res.get('baud_rate', 115200)} baud")
        print(f"Connected:          {res['connected']}")
        print(f"Test Duration:      {res.get('duration_s', verify_dur):.1f}s")
        print(f"Serial Bytes:       {res.get('total_bytes_received', 0)}")
        print(f"Lines Received:     {res.get('total_lines_received', 0)}")
        print(f"Records Detected:   {res.get('total_records_detected', 0)}")
        print(f"Valid CSI Packets:  {res.get('packets_received_during_test', 0)}")
        print(f"Parsing Errors:     {res.get('parse_errors', 0)}")
        print(f"CSI Dimensions:     {res.get('raw_csi_dimensions') or 'N/A'}")
        print(f"Observed Rate:      {res.get('packet_rate_hz', 0.0):.1f} Hz")
        print(f"Mean RSSI:          {res.get('mean_rssi', -99.0):.1f} dBm")
        print(f"Detected Protocol:  {res.get('detected_protocol', 'unknown')}")

        boot_msgs = res.get("boot_messages", [])
        if boot_msgs:
            print("\nRecent Firmware Messages / Boot Telemetry:")
            for bm in boot_msgs[-5:]:
                print(f"  > {bm}")

        print("\nDiagnostic State Summary:")
        state = res.get('diagnostic_state')
        if state == "CSI_STREAM_ACTIVE":
            print("  [SUCCESS] Valid physical CSI packets are actively streaming from ESP32-S3.")
        elif state == "STREAM_INTERRUPTED":
            print("  [WARNING] Packets were received but stream stalled (>2.0s without frame).")
        elif state == "SERIAL_BYTES_NO_VALID_RECORDS":
            print("  [DIAGNOSIS] Serial bytes arrived, but no valid CSI records were detected.")
            print("  Check Wi-Fi connection: Firmware requires active Wi-Fi association to generate CSI.")
        elif state == "RECORDS_RECEIVED_PARSE_FAILED":
            print("  [DIAGNOSIS] Candidate CSI lines were detected, but parsing failed.")
        elif state == "SERIAL_CONNECTED_IDLE":
            print("  [DIAGNOSIS] Port opened, but zero serial bytes were received.")
            print("  The ESP32-S3 may be held in ROM download mode or unpowered.")
        elif state == "SERIAL_DISCONNECTED":
            print(f"  [ERROR] Could not open port {args.port}. Check device manager and permissions.")
        print("=" * 80)
        return

    print("=" * 80)
    print("PHASE 20 — PHYSICAL CSI COLLECTION SESSION")
    print("=" * 80)
    print(f"Activity:       {args.activity.upper()} ({VALID_LABELS[args.activity]['name']})")
    print(f"Participant:    {args.participant}")
    print(f"Duration:       {args.duration:.1f} seconds")
    print(f"Room / Setup:   {args.room} | Distance: {args.distance}m | Orientation: {args.orientation}")
    print(f"Positions:      Tx: {args.tx_pos} | Rx: {args.rx_pos}")
    if args.event:
        print(f"Event ID:       {args.event}")

    if args.activity == "fall":
        print("\n" + "!" * 80)
        print("[MANDATORY SAFETY PROTOCOL]")
        print("1. Ensure a certified minimum 4-inch (10 cm) shock-absorbing crash mat is in place.")
        print("2. A competent spotter must be present. Never fall onto unpadded floors.")
        print("3. Participant must execute controlled breakfall descent. Avoid head/neck impacts.")
        print("4. If safety equipment or supervision is unavailable, POSTPONE the trial.")
        print("!" * 80 + "\n")

    print("Starting session in 1.0s...")
    time.sleep(1.0)

    try:
        rec_start = manager.start_session(
            participant_id=args.participant,
            activity_label=args.activity,
            room_type=args.room,
            tx_rx_distance_m=args.distance,
            tx_position=args.tx_pos,
            rx_position=args.rx_pos,
            orientation=args.orientation,
            duration_seconds=args.duration,
            event_id=args.event,
            notes=args.notes
        )
        print(f"Recording Active: Session ID = {rec_start['session_id']}")
        print(f"                  Event ID   = {rec_start['event_id']}")

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
    print(f"Confirmation Status: {fin_res.get('confirmed')}")
    print("=" * 80)

if __name__ == "__main__":
    main()
