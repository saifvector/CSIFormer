import sys
import os
import time
import re
import numpy as np
import serial

# Ensure project root and backend are on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.services.real_csi_collector import RealCSICollector

def run_detailed_stream_audit(duration_sec=15.0, port="COM5", baud_rate=115200):
    print("=" * 75)
    print("      CSIFormer Phase 51 — High-Fidelity Serial Stream & Payload Audit")
    print("=" * 75)
    print(f"Target Port         : {port}")
    print(f"Baud Rate           : {baud_rate}")
    print(f"Audit Window        : {duration_sec} seconds")
    print(f"Dataset Admission   : STRICTLY FORBIDDEN (Diagnostic Read Only)")

    collector = RealCSICollector(port=port, baud_rate=baud_rate, auto_connect=False)
    
    try:
        ser = serial.Serial(port, baud_rate, timeout=0.1)
    except Exception as e:
        print(f"ERROR: Failed to open serial port {port}: {e}")
        return None

    raw_lines = []
    parsed_records = []
    malformed_lines = []
    total_bytes = 0
    t_start = time.time()
    t_end = t_start + duration_sec

    # Ingest loop with high-resolution timestamps
    line_buffer = bytearray()
    while time.time() < t_end:
        chunk = ser.read(4096)
        if chunk:
            total_bytes += len(chunk)
            line_buffer.extend(chunk)
            while b"\n" in line_buffer:
                idx = line_buffer.find(b"\n")
                line_bytes = line_buffer[:idx+1]
                del line_buffer[:idx+1]
                arrival_time = time.time()
                try:
                    line_str = line_bytes.decode("utf-8", errors="replace").strip()
                except Exception:
                    line_str = ""

                if line_str:
                    raw_lines.append((arrival_time, line_str))
                    # Parse with RealCSICollector parser
                    parsed = collector.parse_raw_telemetry_line(line_str)
                    if parsed:
                        parsed["arrival_time"] = arrival_time
                        parsed_records.append(parsed)
                    elif line_str.startswith("CSI_DATA"):
                        malformed_lines.append((arrival_time, line_str))

    ser.close()
    port_released = not ser.is_open
    actual_duration = time.time() - t_start

    print("\n" + "-" * 75)
    print("                    PHYSICAL SERIAL STREAM METRICS")
    print("-" * 75)
    print(f"Measurement Duration    : {actual_duration:.2f} s")
    print(f"Total Bytes Ingested    : {total_bytes} bytes")
    print(f"Total Lines Processed   : {len(raw_lines)}")
    print(f"Valid CSI_DATA Records  : {len(parsed_records)}")
    print(f"Malformed CSI Records   : {len(malformed_lines)}")
    print(f"Serial Port Released    : {port_released}")

    if not parsed_records:
        print("WARNING: No valid CSI records parsed during audit window!")
        return None

    # Analysis of sequence numbers and packet loss
    sequences = [r["sequence"] for r in parsed_records]
    first_seq, last_seq = sequences[0], sequences[-1]
    expected_packets = (last_seq - first_seq + 1) if last_seq >= first_seq else len(sequences)
    received_packets = len(sequences)
    
    # Calculate exact gaps
    gaps = []
    for i in range(1, len(sequences)):
        diff = sequences[i] - sequences[i-1]
        if diff > 1:
            gaps.append((sequences[i-1], sequences[i], diff - 1))
    
    dropped_packets = sum(g[2] for g in gaps)
    loss_rate_pct = (dropped_packets / expected_packets * 100.0) if expected_packets > 0 else 0.0

    print("\n" + "-" * 75)
    print("                 SEQUENCE & PACKET LOSS DENOMINATOR")
    print("-" * 75)
    print(f"First Sequence ID       : {first_seq}")
    print(f"Last Sequence ID        : {last_seq}")
    print(f"Span of Sequence IDs    : {expected_packets} frames")
    print(f"Actually Received       : {received_packets} frames")
    print(f"Detected Gaps (Drops)   : {len(gaps)} gap instances totaling {dropped_packets} frames")
    print(f"Calculated Packet Loss  : {loss_rate_pct:.2f}% (over serial transport)")

    # Analysis of Inter-Arrival Times & Jitter
    arrival_times = [r["arrival_time"] for r in parsed_records]
    intervals = np.diff(arrival_times)
    mean_interval = float(np.mean(intervals)) if len(intervals) > 0 else 0.0
    std_interval = float(np.std(intervals)) if len(intervals) > 0 else 0.0
    min_interval = float(np.min(intervals)) if len(intervals) > 0 else 0.0
    max_interval = float(np.max(intervals)) if len(intervals) > 0 else 0.0
    instantaneous_rates = [1.0 / dt for dt in intervals if dt > 0]
    mean_rate = float(np.mean(instantaneous_rates)) if instantaneous_rates else 0.0

    print("\n" + "-" * 75)
    print("                 TEMPORAL ARRIVAL & RATE DYNAMICS")
    print("-" * 75)
    print(f"Mean Ingest Rate        : {len(parsed_records) / actual_duration:.2f} Hz")
    print(f"Mean Inter-arrival Time : {mean_interval * 1000.0:.2f} ms")
    print(f"Jitter (Interval StdDev): {std_interval * 1000.0:.2f} ms")
    print(f"Min / Max Interval      : {min_interval * 1000.0:.2f} ms / {max_interval * 1000.0:.2f} ms")

    # Source MAC Distribution
    mac_counts = {}
    rssi_values = []
    noise_values = []
    for r in parsed_records:
        mac_counts[r["mac"]] = mac_counts.get(r["mac"], 0) + 1
        rssi_values.append(r["rssi"])
        noise_values.append(r["noise_floor"])

    print("\n" + "-" * 75)
    print("                 SOURCE TRANSMITTER & SIGNAL QUALITY")
    print("-" * 75)
    for mac, cnt in mac_counts.items():
        print(f"Source BSSID / MAC      : {mac} (Count: {cnt}, {cnt / len(parsed_records) * 100.0:.1f}%)")
    print(f"Mean RSSI               : {np.mean(rssi_values):.1f} dBm (Range: {np.min(rssi_values):.0f} to {np.max(rssi_values):.0f} dBm)")
    print(f"Mean Noise Floor        : {np.mean(noise_values):.1f} dBm (Range: {np.min(noise_values):.0f} to {np.max(noise_values):.0f} dBm)")
    print(f"Estimated SNR           : {np.mean(rssi_values) - np.mean(noise_values):.1f} dB")

    # Physical Subcarrier Analysis
    lengths = [len(r["raw_amplitudes"]) for r in parsed_records]
    len_dist = {}
    for l in lengths:
        len_dist[l] = len_dist.get(l, 0) + 1

    print("\n" + "-" * 75)
    print("                 PHYSICAL SUBCARRIER PAYLOAD STRUCTURE")
    print("-" * 75)
    print(f"Subcarrier Length Distribution: {len_dist}")
    
    # Analyze records grouped by subcarrier length
    for target_len, count in len_dist.items():
        matching = [r for r in parsed_records if len(r["raw_amplitudes"]) == target_len]
        amps = np.array([r["raw_amplitudes"] for r in matching])
        phases = np.array([r["raw_phases"] for r in matching])
        mean_amp = np.mean(amps, axis=0)
        zeros = np.where(mean_amp == 0.0)[0]
        active = np.where(mean_amp > 0.0)[0]
        print(f"\n[Subcarrier Group: {target_len} bins ({count} frames)]")
        print(f"  Active Bins (>0)     : {len(active)} (indices: {active.tolist()[:10]}...)")
        print(f"  Zero / Null Bins (==0): {len(zeros)} (indices: {zeros.tolist()})")
        print(f"  Mean Amp (Active)    : {np.mean(mean_amp[active]):.2f} (min {np.min(mean_amp[active]):.2f}, max {np.max(mean_amp[active]):.2f})")
        print(f"  Phase Range          : {np.min(phases):.3f} to {np.max(phases):.3f} rad")

    print("\n" + "=" * 75)
    print("                        AUDIT SUMMARY VERDICT")
    print("=" * 75)
    print(f"Stream Continuity       : {'PERFECT' if len(gaps) == 0 else f'{len(gaps)} GAPS DETECTED'}")
    print(f"Payload Uniformity      : {'100% UNIFORM (' + str(list(len_dist.keys())[0]) + ' BINS)' if len(len_dist) == 1 else 'VARIABLE: ' + str(len_dist)}")
    print(f"Port Release            : {'CLEANLY RELEASED' if port_released else 'LEAKED'}")
    print("=" * 75)

    return {
        "actual_duration": actual_duration,
        "total_bytes": total_bytes,
        "total_lines": len(raw_lines),
        "valid_records": len(parsed_records),
        "malformed_lines": len(malformed_lines),
        "first_seq": first_seq,
        "last_seq": last_seq,
        "expected_packets": expected_packets,
        "received_packets": received_packets,
        "dropped_packets": dropped_packets,
        "loss_rate_pct": loss_rate_pct,
        "mean_interval_ms": mean_interval * 1000.0,
        "jitter_ms": std_interval * 1000.0,
        "mean_rate_hz": len(parsed_records) / actual_duration,
        "mac_counts": mac_counts,
        "mean_rssi": float(np.mean(rssi_values)),
        "mean_noise": float(np.mean(noise_values)),
        "snr_db": float(np.mean(rssi_values) - np.mean(noise_values)),
        "subcarrier_length_distribution": len_dist,
        "port_released": port_released,
    }

if __name__ == "__main__":
    run_detailed_stream_audit(duration_sec=15.0, port="COM5", baud_rate=115200)
