"""
CSIFormer Phase 53 — Sequence Reconciliation and Transport Audit Script.

Bounded, non-persistent live serial diagnostic on COM5.
Captures raw CSI frames, traces the global sequence counter, reconciles target-filtered
gaps against interleaved non-target transmissions, and quantifies true UART transport loss.
No file writes to dataset, no manifest changes.
"""

import sys
import time
import serial
from typing import List, Dict, Any

TARGET_MAC = "98:BA:5F:EF:28:26"
PORT = "COM5"
BAUD = 115200
SAMPLE_DURATION = 10.0  # seconds

def run_reconciliation_audit():
    print(f"=== Phase 53 Sequence Reconciliation Audit on {PORT} ({SAMPLE_DURATION}s) ===")
    
    # 1. Connect
    try:
        ser = serial.Serial(PORT, BAUD, timeout=1.0)
    except Exception as e:
        print(f"Failed to open {PORT}: {e}")
        return

    # Trigger clean RTS pulse to ensure board is running
    ser.dtr = False
    ser.rts = True
    time.sleep(0.05)
    ser.rts = False
    time.sleep(0.1)
    ser.reset_input_buffer()

    print(f"Connected to {PORT}. Recording frame-by-frame telemetry...")
    start_time = time.time()
    raw_records: List[Dict[str, Any]] = []
    parse_errors = 0

    while time.time() - start_time < SAMPLE_DURATION:
        line_bytes = ser.readline()
        if not line_bytes:
            continue
        try:
            line = line_bytes.decode("utf-8", errors="replace").strip()
        except Exception:
            parse_errors += 1
            continue

        if not line.startswith("CSI_DATA"):
            continue

        parts = line.split(",")
        if len(parts) < 6:
            parse_errors += 1
            continue

        try:
            mac = parts[1].strip().upper()
            rssi = int(parts[2])
            noise = int(parts[3])
            seq = int(parts[4])
            num_sc = int(parts[5])
            is_target = (mac == TARGET_MAC)
            rejection_reason = None if is_target else f"source_mismatch ({mac} != {TARGET_MAC})"
            
            raw_records.append({
                "timestamp": time.time(),
                "seq": seq,
                "mac": mac,
                "rssi": rssi,
                "noise": noise,
                "num_sc": num_sc,
                "is_target": is_target,
                "rejection_reason": rejection_reason
            })
        except Exception:
            parse_errors += 1

    ser.close()
    port_released = not ser.is_open
    print(f"Sampling complete. Port closed: {port_released}\n")

    if not raw_records:
        print("ERROR: No CSI_DATA records captured.")
        return

    # 2. Unfiltered Sequence Analysis (True Transport Loss)
    unfiltered_gaps = 0
    unfiltered_lost_packets = 0
    for i in range(1, len(raw_records)):
        prev_seq = raw_records[i-1]["seq"]
        curr_seq = raw_records[i]["seq"]
        diff = curr_seq - prev_seq
        if diff > 1:
            gap_size = diff - 1
            unfiltered_gaps += 1
            unfiltered_lost_packets += gap_size

    # 3. Target Stream Sequence Analysis (Apparent Gaps)
    target_records = [r for r in raw_records if r["is_target"]]
    non_target_records = [r for r in raw_records if not r["is_target"]]
    
    target_gaps = 0
    target_apparent_lost = 0
    reconciliation_details = []

    for j in range(1, len(target_records)):
        prev_t = target_records[j-1]
        curr_t = target_records[j]
        diff = curr_t["seq"] - prev_t["seq"]
        if diff > 1:
            gap_size = diff - 1
            target_gaps += 1
            target_apparent_lost += gap_size
            
            # Find all non-target records interleaved between prev_t and curr_t
            interleaved = [r for r in non_target_records if prev_t["seq"] < r["seq"] < curr_t["seq"]]
            interleaved_count = len(interleaved)
            unaccounted = gap_size - interleaved_count
            reconciliation_details.append({
                "from_seq": prev_t["seq"],
                "to_seq": curr_t["seq"],
                "gap_size": gap_size,
                "interleaved_non_target": interleaved_count,
                "unaccounted_loss": unaccounted,
                "interleaved_macs": [r["mac"] for r in interleaved]
            })

    # 4. Print Detailed Table
    print("=== Frame Sequence Trace (First 20 Frames) ===")
    print(f"{'Index':<6} {'Seq':<8} {'MAC Address':<20} {'Status':<12} {'Rejection Reason'}")
    print("-" * 75)
    for idx, r in enumerate(raw_records[:20]):
        status = "ADMITTED" if r["is_target"] else "FILTERED"
        reason = r["rejection_reason"] or "Passed (Target AP)"
        print(f"{idx+1:<6} {r['seq']:<8} {r['mac']:<20} {status:<12} {reason}")

    if len(raw_records) > 20:
        print(f"... and {len(raw_records) - 20} more records.")

    print("\n=== Sequence Reconciliation & Gap Breakdown ===")
    print(f"Total Raw CSI Records Captured:    {len(raw_records)}")
    print(f"Target Records Admitted:          {len(target_records)}")
    print(f"Non-Target Records Filtered:      {len(non_target_records)}")
    print(f"Parser Errors:                    {parse_errors}")
    print(f"")
    print(f"--- 1. Unfiltered Global Stream (Firmware -> UART Transport) ---")
    print(f"Unfiltered Sequence Gaps:         {unfiltered_gaps}")
    print(f"Unfiltered Lost Packets:          {unfiltered_lost_packets}")
    if len(raw_records) > 1:
        total_possible = raw_records[-1]["seq"] - raw_records[0]["seq"] + 1
        true_transport_loss_pct = (unfiltered_lost_packets / total_possible) * 100
        print(f"True UART Transport Loss Rate:    {true_transport_loss_pct:.2f}%")
    print(f"")
    print(f"--- 2. Filtered Target Stream (Post-Filter Apparent Loss) ---")
    print(f"Target Stream Sequence Jumps:     {target_gaps}")
    print(f"Target Apparent Missing Packets:  {target_apparent_lost}")
    print(f"Interleaved Non-Target Packets:   {len(non_target_records)}")
    print(f"Reconciliation Match:             {target_apparent_lost == (len(non_target_records) + unfiltered_lost_packets)}")
    print(f"")
    print(f"--- 3. Gap-by-Gap Breakdown in Target Stream ---")
    for d in reconciliation_details:
        print(f"  Target Gap {d['from_seq']} -> {d['to_seq']} (delta={d['gap_size']}): "
              f"{d['interleaved_non_target']} non-target frames observed ({', '.join(set(d['interleaved_macs']))}), "
              f"unaccounted loss = {d['unaccounted_loss']}")

if __name__ == "__main__":
    run_reconciliation_audit()
