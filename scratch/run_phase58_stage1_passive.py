"""
CSIFormer Phase 58 Stage 1: Passive Baseline Capture Engine.

Scope:
- Exactly 30.0 seconds passive serial listening on COM5 @ 115200 baud.
- Target MAC: 98:BA:5F:EF:28:26
- Read-only: Zero serial transmission, zero DTR/RTS toggling/resetting.
- Zero network traffic: No UDP, no ICMP ping, no stimulation.
- Zero firmware flashing or building.
- Zero model execution or dataset mutation.
"""

import sys
import os
import time
import json
import math
import re
from typing import Dict, Any, List
import serial
import serial.tools.list_ports
import numpy as np

# Ensure backend modules can be imported
sys.path.insert(0, os.path.abspath("backend"))
sys.path.insert(0, os.path.abspath("."))
from backend.app.services.real_csi_collector import RealCSICollector

PORT = "COM5"
BAUD = 115200
TARGET_MAC = "98:BA:5F:EF:28:26"
CAPTURE_DURATION_S = 30.0

def preflight_check() -> Dict[str, Any]:
    ports = list(serial.tools.list_ports.comports())
    com5_info = None
    for p in ports:
        if p.device.upper() == PORT:
            com5_info = {
                "device": p.device,
                "description": p.description,
                "hwid": p.hwid,
                "manufacturer": p.manufacturer
            }
            break
    return {
        "port_found": com5_info is not None,
        "details": com5_info,
        "all_ports": [p.device for p in ports]
    }

def run_passive_capture() -> Dict[str, Any]:
    pre = preflight_check()
    if not pre["port_found"]:
        return {
            "status": "BLOCKED",
            "reason": f"Port {PORT} not found among system serial ports: {pre['all_ports']}",
            "preflight": pre
        }

    collector = RealCSICollector(
        port=PORT,
        baud_rate=BAUD,
        target_mac=TARGET_MAC,
        filter_by_mac=True
    )

    # Passive open with dtr=False, rts=False
    ser = serial.Serial()
    ser.port = PORT
    ser.baudrate = BAUD
    ser.timeout = 0.1
    ser.write_timeout = 1.0
    ser.dtr = False
    ser.rts = False

    try:
        ser.open()
    except Exception as e:
        return {
            "status": "BLOCKED",
            "reason": f"Failed to open {PORT} passively: {e}",
            "preflight": pre
        }

    # Ensure buffer is not holding stale garbage from hours ago
    ser.reset_input_buffer()

    sample_raw_lines = []
    all_raw_lines = []
    records = []
    source_mac_counts = {}
    parse_errors = 0
    total_raw_lines = 0
    candidate_records = 0

    last_fw_seq = None
    firmware_sequence_gaps = 0
    duplicate_packets = 0
    out_of_order_packets = 0
    counter_resets = 0

    last_target_seq = None
    target_sequence_gaps = 0

    detected_protocol = "unknown"
    has_v2_fields = False

    start_perf = time.perf_counter()
    start_wall = time.time()
    end_perf = start_perf + CAPTURE_DURATION_S

    print(f"=== Starting 30.0s Passive Capture on {PORT} @ {BAUD} baud ===")
    print(f"Start time (wall): {start_wall:.3f}")
    print(f"Target MAC: {TARGET_MAC}")
    print("Safety: Read-only, RTS=False, DTR=False, zero network traffic.")

    line_buffer = ""

    while time.perf_counter() < end_perf:
        try:
            in_w = ser.in_waiting or 1
            raw_bytes = ser.read(in_w)
            if not raw_bytes:
                continue

            chunk = raw_bytes.decode("ascii", errors="replace")
            line_buffer += chunk

            while "\n" in line_buffer:
                line, line_buffer = line_buffer.split("\n", 1)
                line = line.strip()
                if not line:
                    continue

                total_raw_lines += 1
                arrival_perf = time.perf_counter()
                arrival_wall = time.time()

                if len(sample_raw_lines) < 10:
                    sample_raw_lines.append(line[:120])

                is_candidate = ("RSSI=" in line and "CSI:" in line) or line.startswith("CSI_DATA")
                if not is_candidate:
                    continue

                candidate_records += 1

                # Parse record
                parsed = collector.parse_raw_telemetry_line(line)
                if parsed is None:
                    parse_errors += 1
                    continue

                if collector.detected_protocol:
                    detected_protocol = collector.detected_protocol
                if "hw_timestamp_us" in parsed or "rx_seq" in parsed:
                    has_v2_fields = True

                seq = parsed.get("sequence")
                mac = parsed.get("mac", "").upper()
                rssi = parsed.get("rssi")
                noise = parsed.get("noise_floor")
                num_sc = parsed.get("num_subcarriers")

                source_mac_counts[mac] = source_mac_counts.get(mac, 0) + 1

                # Sequence tracking across all valid firmware records
                if seq is not None:
                    if last_fw_seq is not None:
                        if seq > last_fw_seq:
                            gap = seq - (last_fw_seq + 1)
                            if gap > 0:
                                firmware_sequence_gaps += gap
                            last_fw_seq = seq
                        elif seq < last_fw_seq:
                            if last_fw_seq > 0xFFFF0000 and seq < 0x10000:
                                gap = (seq + 0x100000000) - (last_fw_seq + 1)
                                if gap > 0:
                                    firmware_sequence_gaps += gap
                                last_fw_seq = seq
                            elif (last_fw_seq - seq) > 1000 or (last_fw_seq >= 100 and seq <= 10):
                                counter_resets += 1
                                last_fw_seq = seq
                            else:
                                out_of_order_packets += 1
                        else:
                            duplicate_packets += 1
                    else:
                        last_fw_seq = seq

                is_target = (mac == TARGET_MAC)
                if is_target and seq is not None:
                    if last_target_seq is not None:
                        if seq > last_target_seq:
                            t_gap = seq - (last_target_seq + 1)
                            if t_gap > 0:
                                target_sequence_gaps += t_gap
                        elif seq < last_target_seq:
                            if last_target_seq > 0xFFFF0000 and seq < 0x10000:
                                t_gap = (seq + 0x100000000) - (last_target_seq + 1)
                                if t_gap > 0:
                                    target_sequence_gaps += t_gap
                    last_target_seq = seq

                records.append({
                    "perf_time": arrival_perf,
                    "wall_time": arrival_wall,
                    "seq": seq,
                    "mac": mac,
                    "is_target": is_target,
                    "rssi": rssi,
                    "noise": noise,
                    "num_sc": num_sc
                })

        except Exception as e:
            print(f"Read error during capture: {e}")
            break

    stop_perf = time.perf_counter()
    stop_wall = time.time()
    actual_duration_s = stop_perf - start_perf

    # Clean port release
    ser.close()
    port_released = not ser.is_open

    print(f"=== Capture Finished: Actual Duration = {actual_duration_s:.3f} s ===")
    print(f"Port released: {port_released}")

    # Metrics computation
    total_valid_records = len(records)
    target_records = [r for r in records if r["is_target"]]
    non_target_records = [r for r in records if not r["is_target"]]

    target_count = len(target_records)
    non_target_count = len(non_target_records)

    # Inter-arrival statistics (target)
    target_intervals = []
    if target_count >= 2:
        target_intervals = [
            target_records[i]["perf_time"] - target_records[i - 1]["perf_time"]
            for i in range(1, target_count)
        ]

    # Inter-arrival statistics (all valid records)
    all_intervals = []
    if total_valid_records >= 2:
        all_intervals = [
            records[i]["perf_time"] - records[i - 1]["perf_time"]
            for i in range(1, total_valid_records)
        ]

    def stats_dict(intervals: List[float], count: int, dur: float) -> Dict[str, Any]:
        if not intervals or count < 2:
            rate = round(count / dur, 3) if dur > 0 else 0.0
            return {
                "count": count,
                "rate_hz": rate,
                "mean_interval_ms": None,
                "std_interval_ms": None,
                "min_interval_ms": None,
                "max_interval_ms": None,
                "p50_interval_ms": None,
                "p95_interval_ms": None
            }
        arr_ms = np.array(intervals) * 1000.0
        rate = round(count / dur, 3)
        return {
            "count": count,
            "rate_hz": rate,
            "mean_interval_ms": round(float(np.mean(arr_ms)), 2),
            "std_interval_ms": round(float(np.std(arr_ms)), 2),
            "min_interval_ms": round(float(np.min(arr_ms)), 2),
            "max_interval_ms": round(float(np.max(arr_ms)), 2),
            "p50_interval_ms": round(float(np.percentile(arr_ms, 50)), 2),
            "p95_interval_ms": round(float(np.percentile(arr_ms, 95)), 2)
        }

    target_stats = stats_dict(target_intervals, target_count, actual_duration_s)
    all_stats = stats_dict(all_intervals, total_valid_records, actual_duration_s)

    report = {
        "status": "COMPLETED" if total_valid_records > 0 else "INCONCLUSIVE",
        "preflight": pre,
        "timing": {
            "target_duration_s": CAPTURE_DURATION_S,
            "actual_duration_s": round(actual_duration_s, 4),
            "start_wall": start_wall,
            "stop_wall": stop_wall,
            "start_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(start_wall)),
            "stop_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(stop_wall))
        },
        "port_released": port_released,
        "telemetry_format": {
            "detected_protocol": detected_protocol,
            "has_v2_fields": has_v2_fields,
            "sample_lines": sample_raw_lines[:5]
        },
        "counts": {
            "total_raw_lines": total_raw_lines,
            "candidate_records": candidate_records,
            "valid_records_parsed": total_valid_records,
            "target_records": target_count,
            "filtered_non_target_records": non_target_count,
            "parse_errors": parse_errors
        },
        "sequence_metrics": {
            "firmware_sequence_gaps": firmware_sequence_gaps,
            "target_sequence_gaps": target_sequence_gaps,
            "duplicate_packets": duplicate_packets,
            "out_of_order_packets": out_of_order_packets,
            "counter_resets": counter_resets
        },
        "source_mac_distribution": source_mac_counts,
        "arrival_timing": {
            "target_traffic": target_stats,
            "aggregate_traffic": all_stats
        }
    }

    return report

if __name__ == "__main__":
    result = run_passive_capture()
    print("\n--- JSON OUTPUT ---")
    print(json.dumps(result, indent=2))
