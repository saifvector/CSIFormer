"""
CSIFormer Phase 54 — Controlled 2.4 GHz Acquisition-Rate Experiment Engine.

Active Link: 2.4 GHz (Channel 7, BSSID: 98:ba:5f:ef:28:26)
Destination: 192.168.0.1 (Unicast ICMP)

Stage 0: 10.0s Passive Baseline (0 pkts/s).
Stage 1: 10.0s Unicast ICMP (5 pkts/s -> 192.168.0.1).

Abort Conditions:
- Router latency > 50 ms on any probe.
- Measured probe loss > 2.0% (e.g. > 1 drop in 50).
- UART transport loss > 2.0%.
- Serial disconnect or buffer overflow.

Zero persistent dataset writes, zero manifest changes.
"""

import sys
import time
import subprocess
import threading
import serial
import numpy as np
from typing import List, Dict, Any

TARGET_MAC = "98:BA:5F:EF:28:26"
ROUTER_IP = "192.168.0.1"
PORT = "COM5"
BAUD = 115200

def capture_serial_csi(port: str, baud: int, duration_sec: float, stop_event: threading.Event) -> Dict[str, Any]:
    """Captures and parses CSI_DATA lines from the serial port for duration_sec."""
    results = {
        "raw_records": [],
        "parse_errors": 0,
        "port_released": False,
        "error": None
    }
    
    try:
        ser = serial.Serial(port, baud, timeout=0.5)
    except Exception as e:
        results["error"] = str(e)
        return results

    # Pulse RTS to guarantee ESP32-S3 is running in normal application mode
    try:
        ser.dtr = False
        ser.rts = True
        time.sleep(0.05)
        ser.rts = False
        time.sleep(0.1)
        ser.reset_input_buffer()
    except Exception:
        pass

    start_time = time.time()
    while time.time() - start_time < duration_sec and not stop_event.is_set():
        line_bytes = ser.readline()
        if not line_bytes:
            continue
        try:
            line = line_bytes.decode("utf-8", errors="replace").strip()
        except Exception:
            results["parse_errors"] += 1
            continue

        if not line.startswith("CSI_DATA"):
            continue

        parts = line.split(",")
        if len(parts) < 6:
            results["parse_errors"] += 1
            continue

        try:
            mac = parts[1].strip().upper()
            rssi = int(parts[2])
            noise = int(parts[3])
            seq = int(parts[4])
            num_sc = int(parts[5])
            now = time.time()
            
            results["raw_records"].append({
                "timestamp": now,
                "seq": seq,
                "mac": mac,
                "rssi": rssi,
                "noise": noise,
                "num_sc": num_sc,
                "is_target": (mac == TARGET_MAC)
            })
        except Exception:
            results["parse_errors"] += 1

    try:
        ser.close()
        results["port_released"] = not ser.is_open
    except Exception:
        results["port_released"] = False

    return results

def run_unicast_ping_train(dest_ip: str, rate_hz: float, duration_sec: float, stop_event: threading.Event) -> Dict[str, Any]:
    """
    Sends calibrated unicast ICMP echo requests at rate_hz for duration_sec.
    Enforces real-time abort checks:
    - RTT > 50 ms -> immediate stop.
    - Probe loss > 2.0% -> immediate stop.
    """
    stats = {
        "transmitted": 0,
        "received": 0,
        "rtt_ms": [],
        "loss_pct": 0.0,
        "aborted_reason": None
    }
    
    interval = 1.0 / rate_hz
    end_time = time.time() + duration_sec
    
    while time.time() < end_time and not stop_event.is_set():
        t0 = time.time()
        stats["transmitted"] += 1
        
        try:
            res = subprocess.run(
                ["ping", "-n", "1", "-w", "500", dest_ip],
                capture_output=True,
                text=True,
                timeout=1.0
            )
            out = res.stdout
            rtt = None
            if "bytes=" in out or "time=" in out or "time<" in out:
                stats["received"] += 1
                if "time=" in out:
                    part = out.split("time=")[1].split("ms")[0].strip()
                    try:
                        rtt = float(part)
                    except Exception:
                        rtt = 1.0
                elif "time<1ms" in out or "time<" in out:
                    rtt = 0.5
                stats["rtt_ms"].append(rtt)
                
                # Real-time Abort Check 1: Latency > 50 ms
                if rtt is not None and rtt > 50.0:
                    stats["aborted_reason"] = f"latency_exceeded_50ms (measured {rtt} ms)"
                    print(f"\n[ABORT TRIGGER] Ping latency exceeded 50 ms: {rtt} ms!")
                    stop_event.set()
                    break
            else:
                # Packet lost
                lost_so_far = stats["transmitted"] - stats["received"]
                # Real-time Abort Check 2: Loss > 2% (more than 1 lost packet in up to 50)
                if lost_so_far > 1:
                    stats["aborted_reason"] = f"loss_exceeded_2pct (lost {lost_so_far}/{stats['transmitted']})"
                    print(f"\n[ABORT TRIGGER] Probe loss exceeded 2.0%: lost {lost_so_far}/{stats['transmitted']}!")
                    stop_event.set()
                    break

        except Exception as e:
            stats["aborted_reason"] = f"ping_exception: {e}"
            stop_event.set()
            break

        elapsed = time.time() - t0
        sleep_dur = max(0.001, interval - elapsed)
        time.sleep(sleep_dur)

    total = stats["transmitted"]
    lost = total - stats["received"]
    stats["loss_pct"] = round((lost / total * 100), 1) if total > 0 else 0.0
    return stats

def analyze_csi_stage(records: List[Dict[str, Any]], parse_errors: int, duration_sec: float) -> Dict[str, Any]:
    """Analyzes raw CSI telemetry for transport loss, target filtering, and inter-arrival timing."""
    total_records = len(records)
    target_records = [r for r in records if r["is_target"]]
    non_target_records = [r for r in records if not r["is_target"]]
    
    # Unfiltered transport loss check (firmware -> host UART)
    unfiltered_gaps = 0
    unfiltered_lost = 0
    for i in range(1, len(records)):
        diff = records[i]["seq"] - records[i-1]["seq"]
        if diff > 1:
            unfiltered_gaps += 1
            unfiltered_lost += (diff - 1)
            
    # Target stream analysis
    target_count = len(target_records)
    target_rate_hz = round(target_count / duration_sec, 2) if duration_sec > 0 else 0.0
    
    # Inter-arrival times for target frames
    iat = []
    for j in range(1, len(target_records)):
        dt = target_records[j]["timestamp"] - target_records[j-1]["timestamp"]
        iat.append(dt * 1000.0) # in ms
        
    iat_mean = round(float(np.mean(iat)), 2) if iat else 0.0
    iat_std = round(float(np.std(iat)), 2) if iat else 0.0
    iat_min = round(float(np.min(iat)), 2) if iat else 0.0
    iat_max = round(float(np.max(iat)), 2) if iat else 0.0
    
    return {
        "duration_sec": duration_sec,
        "total_records": total_records,
        "target_records": target_count,
        "non_target_records": len(non_target_records),
        "parse_errors": parse_errors,
        "unfiltered_gaps": unfiltered_gaps,
        "unfiltered_lost_pkts": unfiltered_lost,
        "transport_loss_pct": round((unfiltered_lost / max(1, total_records + unfiltered_lost) * 100), 2),
        "target_rate_hz": target_rate_hz,
        "target_iat_mean_ms": iat_mean,
        "target_iat_std_ms": iat_std,
        "target_iat_min_ms": iat_min,
        "target_iat_max_ms": iat_max,
        "non_target_macs": list(set(r["mac"] for r in non_target_records))
    }

def run_experiment():
    print("=" * 75)
    print("   CSIFormer Phase 54: Controlled 2.4 GHz Acquisition-Rate Experiment")
    print("=" * 75)
    print(f"Target AP BSSID:    {TARGET_MAC} (Channel 7, 2.442 GHz)")
    print(f"Router Destination: {ROUTER_IP} (Unicast ICMP)")
    print(f"Serial Interface:   {PORT} @ {BAUD} baud")
    print()

    # ---------------------------------------------------------
    # STAGE 0: Passive Baseline (0 pkts/s, 10s)
    # ---------------------------------------------------------
    print(">>> Executing Stage 0: 2.4 GHz Passive Baseline (10.0s, 0 pkts/s)...")
    stop_ev = threading.Event()
    t_start = time.time()
    csi_out_0 = capture_serial_csi(PORT, BAUD, 10.0, stop_ev)
    actual_dur_0 = round(time.time() - t_start, 2)
    
    metrics_0 = analyze_csi_stage(csi_out_0["raw_records"], csi_out_0["parse_errors"], actual_dur_0)
    print(f"Stage 0 Completed in {actual_dur_0}s.")
    print(f"  - Total Captured Records:     {metrics_0['total_records']}")
    print(f"  - Target AP Records Admitted: {metrics_0['target_records']}")
    print(f"  - Non-Target Records Filtered:{metrics_0['non_target_records']} ({metrics_0['non_target_macs']})")
    print(f"  - Unfiltered Transport Gaps:  {metrics_0['unfiltered_gaps']} (Loss: {metrics_0['transport_loss_pct']}%)")
    print(f"  - Target CSI Record Rate:     {metrics_0['target_rate_hz']} Hz")
    print(f"  - Inter-Arrival Jitter (std): {metrics_0['target_iat_std_ms']} ms (mean={metrics_0['target_iat_mean_ms']} ms)")
    print(f"  - Port Released:              {csi_out_0['port_released']}")
    print()

    # Safety check before Stage 1
    if metrics_0["transport_loss_pct"] > 2.0:
        print("ERROR: Baseline UART transport loss exceeds 2.0%. Aborting.")
        return

    # ---------------------------------------------------------
    # STAGE 1: Unicast ICMP at 5 pkts/s (10.0s) on 2.4 GHz Link
    # ---------------------------------------------------------
    print(">>> Executing Stage 1: Unicast ICMP (5 pkts/s -> 192.168.0.1 for 10.0s on 2.4 GHz)...")
    stop_ev_1 = threading.Event()
    ping_results_1 = {}
    csi_results_1 = {}
    
    def ping_worker():
        nonlocal ping_results_1
        ping_results_1 = run_unicast_ping_train(ROUTER_IP, rate_hz=5.0, duration_sec=10.0, stop_event=stop_ev_1)
        
    def csi_worker():
        nonlocal csi_results_1
        csi_results_1 = capture_serial_csi(PORT, BAUD, duration_sec=10.0, stop_event=stop_ev_1)
        
    t_th_ping = threading.Thread(target=ping_worker)
    t_th_csi = threading.Thread(target=csi_worker)
    
    t_start_1 = time.time()
    t_th_ping.start()
    t_th_csi.start()
    
    t_th_ping.join()
    t_th_csi.join()
    actual_dur_1 = round(time.time() - t_start_1, 2)
    
    metrics_1 = analyze_csi_stage(csi_results_1["raw_records"], csi_results_1["parse_errors"], actual_dur_1)
    
    rtt_mean = round(float(np.mean(ping_results_1["rtt_ms"])), 2) if ping_results_1.get("rtt_ms") else 0.0
    rtt_max = round(float(np.max(ping_results_1["rtt_ms"])), 2) if ping_results_1.get("rtt_ms") else 0.0
    
    print(f"Stage 1 Completed in {actual_dur_1}s.")
    print(f"  - ICMP Probes Transmitted:    {ping_results_1['transmitted']}")
    print(f"  - ICMP Responses Received:   {ping_results_1['received']} (Loss: {ping_results_1['loss_pct']}%)")
    print(f"  - Router RTT Mean / Max:      {rtt_mean} ms / {rtt_max} ms")
    if ping_results_1.get("aborted_reason"):
        print(f"  - WARNING: Stage was aborted: {ping_results_1['aborted_reason']}")
    print(f"  - Total Captured Records:     {metrics_1['total_records']}")
    print(f"  - Target AP Records Admitted: {metrics_1['target_records']}")
    print(f"  - Non-Target Records Filtered:{metrics_1['non_target_records']} ({metrics_1['non_target_macs']})")
    print(f"  - Unfiltered Transport Gaps:  {metrics_1['unfiltered_gaps']} (Loss: {metrics_1['transport_loss_pct']}%)")
    print(f"  - Target CSI Record Rate:     {metrics_1['target_rate_hz']} Hz")
    print(f"  - Inter-Arrival Jitter (std): {metrics_1['target_iat_std_ms']} ms (mean={metrics_1['target_iat_mean_ms']} ms)")
    print(f"  - Port Released:              {csi_results_1['port_released']}")
    print()

    # ---------------------------------------------------------
    # COMPARISON & SUMMARY
    # ---------------------------------------------------------
    probe_summary_0 = "0 / 0"
    probe_summary_1 = str(ping_results_1['transmitted']) + " / " + str(ping_results_1['received'])
    rtt_summary_0 = "N/A"
    rtt_summary_1 = str(rtt_mean) + " ms"
    iat_0_str = str(metrics_0['target_iat_mean_ms']) + " (" + str(metrics_0['target_iat_std_ms']) + ") ms"
    iat_1_str = str(metrics_1['target_iat_mean_ms']) + " (" + str(metrics_1['target_iat_std_ms']) + ") ms"

    print("=" * 75)
    print("   STAGE 0 vs STAGE 1 COMPARATIVE ANALYSIS (DIRECT 2.4 GHz LINK)")
    print("=" * 75)
    print(f"{'Metric':<30} {'Stage 0 (Passive)':<22} {'Stage 1 (5 Hz ICMP 2.4G)':<22}")
    print("-" * 75)
    print(f"{'Configured Probe Rate':<30} {'0 pkts/s':<22} {'5 pkts/s':<22}")
    print(f"{'Actual Duration':<30} {str(actual_dur_0) + ' s':<22} {str(actual_dur_1) + ' s':<22}")
    print(f"{'Probes Sent / Acked':<30} {probe_summary_0:<22} {probe_summary_1:<22}")
    print(f"{'Router Mean Latency':<30} {rtt_summary_0:<22} {rtt_summary_1:<22}")
    print(f"{'Total Raw CSI Records':<30} {str(metrics_0['total_records']):<22} {str(metrics_1['total_records']):<22}")
    print(f"{'Target Records Admitted':<30} {str(metrics_0['target_records']):<22} {str(metrics_1['target_records']):<22}")
    print(f"{'Non-Target Records Filtered':<30} {str(metrics_0['non_target_records']):<22} {str(metrics_1['non_target_records']):<22}")
    print(f"{'Target CSI Rate':<30} {str(metrics_0['target_rate_hz']) + ' Hz':<22} {str(metrics_1['target_rate_hz']) + ' Hz':<22}")
    print(f"{'Target IAT Mean (Std)':<30} {iat_0_str:<22} {iat_1_str:<22}")
    print(f"{'UART Transport Loss':<30} {str(metrics_0['transport_loss_pct']) + ' %':<22} {str(metrics_1['transport_loss_pct']) + ' %':<22}")
    print(f"{'Port Released Cleanly':<30} {str(csi_out_0['port_released']):<22} {str(csi_results_1['port_released']):<22}")
    print("=" * 75)

if __name__ == "__main__":
    run_experiment()
