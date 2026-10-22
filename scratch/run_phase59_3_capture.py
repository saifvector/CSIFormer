"""
CSIFormer Phase 59.3 — Passive Real ESP32-S3 Hardware Capture.

Duration: ~30.0 seconds
Port: COM5 @ 115200 baud
Target Router MAC: 98:BA:5F:EF:28:26 (TP-Link Archer C6)
Mode: Strictly Passive (dtr=False, rts=False, zero serial writes, zero network traffic)
Storage: Dedicated session directory isolated from canonical dataset:
         - reports/evidence/phase59_3_capture/
         - data/real_capture_phase59_3/
"""

import sys
import os
import time
import json
import hashlib
from pathlib import Path

# Add project root and backend to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend"))
sys.path.insert(0, str(PROJECT_ROOT))

from app.services.real_csi_collector import RealCSICollector
import serial
import serial.tools.list_ports

PORT = "COM5"
BAUD = 115200
TARGET_MAC = "98:BA:5F:EF:28:26"
CAPTURE_DURATION_S = 30.0

EVIDENCE_DIR = PROJECT_ROOT / "reports" / "evidence" / "phase59_3_capture"
DATA_DIR = PROJECT_ROOT / "data" / "real_capture_phase59_3"

def main():
    print(f"=== CSIFormer Phase 59.3 Real Hardware Capture ===")
    print(f"Port: {PORT} @ {BAUD} baud")
    print(f"Target MAC: {TARGET_MAC}")
    print(f"Duration: {CAPTURE_DURATION_S} seconds")

    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Preflight check
    ports = [p.device for p in serial.tools.list_ports.comports()]
    if PORT not in ports:
        print(f"ERROR: {PORT} not found in available ports: {ports}")
        sys.exit(1)

    timestamp_str = time.strftime("%Y%m%d_%H%M%S", time.gmtime())
    session_id = f"phase59_3_real_csi_{timestamp_str}"

    collector = RealCSICollector(
        port=PORT,
        baud_rate=BAUD,
        target_mac=TARGET_MAC,
        filter_by_mac=False, # We want to capture all frames and count target vs non-target
        data_dir=str(DATA_DIR)
    )

    # Passive serial opening
    ser = serial.Serial()
    ser.port = PORT
    ser.baudrate = BAUD
    ser.timeout = 0.1
    ser.write_timeout = 1.0
    ser.dtr = False
    ser.rts = False
    ser.open()
    ser.reset_input_buffer()

    print(f"Port {PORT} opened passively. Starting {CAPTURE_DURATION_S}s capture...")

    records = []
    sample_lines = []
    source_mac_counts = {}
    total_lines = 0
    candidate_lines = 0
    parsed_valid_frames = 0
    target_frames = 0
    non_target_frames = 0
    parse_errors = 0

    last_fw_seq = None
    fw_gaps = 0
    target_gaps = 0
    last_target_seq = None

    start_mono = time.perf_counter()
    start_wall = time.time()
    end_mono = start_mono + CAPTURE_DURATION_S

    line_buffer = ""

    jsonl_path = EVIDENCE_DIR / f"{session_id}_records.jsonl"
    with open(jsonl_path, "w", encoding="utf-8") as jsonl_file:
        while time.perf_counter() < end_mono:
            in_w = ser.in_waiting or 1
            raw_bytes = ser.read(in_w)
            if not raw_bytes:
                continue

            text = raw_bytes.decode("utf-8", errors="replace")
            combined = line_buffer + text
            while "\n" in combined:
                raw_line, combined = combined.split("\n", 1)
                clean_line = raw_line.rstrip("\r\n")
                line_buffer = combined

                if not clean_line.strip():
                    continue

                now_mono = time.perf_counter()
                now_wall = time.time()
                total_lines += 1

                if len(sample_lines) < 10:
                    sample_lines.append(clean_line[:120])

                is_candidate = clean_line.startswith("CSI_DATA") or ("RSSI=" in clean_line and "CSI:" in clean_line)
                if not is_candidate:
                    rec = {
                        "line_index": total_lines,
                        "host_monotonic": round(now_mono, 6),
                        "host_wall": round(now_wall, 6),
                        "status": "NON_CSI_LINE",
                        "raw_line": clean_line
                    }
                    jsonl_file.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    continue

                candidate_lines += 1
                parsed = collector.parse_raw_telemetry_line(clean_line)
                if parsed is None:
                    parse_errors += 1
                    rec = {
                        "line_index": total_lines,
                        "host_monotonic": round(now_mono, 6),
                        "host_wall": round(now_wall, 6),
                        "status": "PARSER_ERROR",
                        "raw_line": clean_line
                    }
                    jsonl_file.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    continue

                parsed_valid_frames += 1
                mac = str(parsed.get("mac", "")).upper()
                source_mac_counts[mac] = source_mac_counts.get(mac, 0) + 1
                seq = parsed.get("sequence")

                if seq is not None:
                    if last_fw_seq is not None and seq > last_fw_seq:
                        gap = seq - (last_fw_seq + 1)
                        if gap > 0:
                            fw_gaps += gap
                    last_fw_seq = seq

                is_target = (mac == TARGET_MAC)
                if is_target:
                    target_frames += 1
                    if seq is not None:
                        if last_target_seq is not None and seq > last_target_seq:
                            tgap = seq - (last_target_seq + 1)
                            if tgap > 0:
                                target_gaps += tgap
                        last_target_seq = seq
                else:
                    non_target_frames += 1

                # Subcarrier alignment to 56
                raw_amps = parsed.get("raw_amplitudes", [])
                raw_phases = parsed.get("raw_phases", [])
                import numpy as np
                if len(raw_amps) != 56 and len(raw_amps) > 0:
                    x_old = np.linspace(0, 1, len(raw_amps))
                    x_new = np.linspace(0, 1, 56)
                    aligned_amps = np.interp(x_new, x_old, raw_amps).astype(float).tolist()
                    aligned_phases = np.interp(x_new, x_old, raw_phases).astype(float).tolist()
                else:
                    aligned_amps = [float(a) for a in raw_amps]
                    aligned_phases = [float(p) for p in raw_phases]

                rec = {
                    "line_index": total_lines,
                    "host_monotonic": round(now_mono, 6),
                    "host_wall": round(now_wall, 6),
                    "status": "VALID_TARGET" if is_target else "FILTERED_NON_TARGET",
                    "mac": mac,
                    "rssi": parsed.get("rssi"),
                    "noise": parsed.get("noise_floor"),
                    "sequence": seq,
                    "raw_num_subcarriers": len(raw_amps),
                    "raw_amplitudes": raw_amps,
                    "raw_phases": raw_phases,
                    "aligned_amplitudes_56": aligned_amps,
                    "aligned_phases_56": aligned_phases,
                    "raw_line": clean_line
                }
                records.append(rec)
                jsonl_file.write(json.dumps(rec, ensure_ascii=False) + "\n")

    stop_mono = time.perf_counter()
    stop_wall = time.time()
    ser.close()

    actual_duration = stop_mono - start_mono
    print(f"Capture complete. Duration: {actual_duration:.2f}s")
    print(f"Total lines: {total_lines}")
    print(f"Candidate lines: {candidate_lines}")
    print(f"Valid parsed frames: {parsed_valid_frames}")
    print(f"Target frames ({TARGET_MAC}): {target_frames}")
    print(f"Non-target frames: {non_target_frames}")
    print(f"Parse errors: {parse_errors}")
    print(f"Source MAC distribution: {source_mac_counts}")
    print(f"Observed Target rate: {target_frames / actual_duration:.2f} Hz")
    print(f"Observed Aggregate rate: {parsed_valid_frames / actual_duration:.2f} Hz")

    # Serialize complete session JSON and CSV
    session_json_path = DATA_DIR / f"{session_id}.json"
    session_csv_path = DATA_DIR / f"{session_id}.csv"

    session_data = {
        "session_id": session_id,
        "capture_date": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(start_wall)),
        "port": PORT,
        "baud_rate": BAUD,
        "target_mac": TARGET_MAC,
        "actual_duration_s": round(actual_duration, 4),
        "total_lines": total_lines,
        "candidate_lines": candidate_lines,
        "valid_parsed_frames": parsed_valid_frames,
        "target_frames": target_frames,
        "non_target_frames": non_target_frames,
        "parse_errors": parse_errors,
        "target_packet_rate_hz": round(target_frames / actual_duration, 2),
        "aggregate_packet_rate_hz": round(parsed_valid_frames / actual_duration, 2),
        "source_mac_distribution": source_mac_counts,
        "sequence_metrics": {
            "firmware_sequence_gaps": fw_gaps,
            "target_sequence_gaps": target_gaps
        },
        "frames": records
    }

    with open(session_json_path, "w", encoding="utf-8") as f:
        json.dump(session_data, f, indent=2)

    import csv
    with open(session_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        header = ["timestamp", "host_monotonic", "sequence", "mac", "rssi", "noise", "status", "raw_num_sc"]
        header += [f"amp_{i}" for i in range(56)]
        writer.writerow(header)
        for r in records:
            row = [
                r["host_wall"],
                r["host_monotonic"],
                r["sequence"],
                r["mac"],
                r["rssi"],
                r["noise"],
                r["status"],
                r["raw_num_subcarriers"]
            ]
            row.extend(r.get("aligned_amplitudes_56", []))
            writer.writerow(row)

    # Manifest with MD5
    with open(session_json_path, "rb") as f:
        json_md5 = hashlib.md5(f.read()).hexdigest()
    with open(session_csv_path, "rb") as f:
        csv_md5 = hashlib.md5(f.read()).hexdigest()
    with open(jsonl_path, "rb") as f:
        jsonl_md5 = hashlib.md5(f.read()).hexdigest()

    manifest = {
        "session_id": session_id,
        "target_mac": TARGET_MAC,
        "timing": {
            "start_wall": start_wall,
            "stop_wall": stop_wall,
            "start_monotonic": start_mono,
            "stop_monotonic": stop_mono,
            "actual_duration_s": round(actual_duration, 4)
        },
        "counts": {
            "total_lines": total_lines,
            "candidate_lines": candidate_lines,
            "valid_parsed_frames": parsed_valid_frames,
            "target_frames": target_frames,
            "non_target_frames": non_target_frames,
            "parse_errors": parse_errors
        },
        "rates": {
            "target_rate_hz": round(target_frames / actual_duration, 4),
            "aggregate_rate_hz": round(parsed_valid_frames / actual_duration, 4)
        },
        "source_mac_distribution": source_mac_counts,
        "artifacts": {
            "session_json": str(session_json_path),
            "session_json_md5": json_md5,
            "session_csv": str(session_csv_path),
            "session_csv_md5": csv_md5,
            "jsonl_evidence": str(jsonl_path),
            "jsonl_evidence_md5": jsonl_md5
        }
    }

    manifest_path = EVIDENCE_DIR / f"{session_id}_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"\nCapture saved successfully:")
    print(f"  JSON: {session_json_path} (MD5: {json_md5})")
    print(f"  CSV:  {session_csv_path} (MD5: {csv_md5})")
    print(f"  JSONL: {jsonl_path} (MD5: {jsonl_md5})")
    print(f"  Manifest: {manifest_path}")

if __name__ == "__main__":
    main()
