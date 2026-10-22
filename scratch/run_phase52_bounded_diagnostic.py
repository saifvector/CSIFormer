"""
Bounded, Non-Persistent Phase 52 Live CSI Stream Diagnostic Script.

Connects to COM5 for 10 seconds, collects live CSI telemetry, applies target-source
filtering (target MAC: 98:BA:5F:EF:28:26), records stream diagnostics, and disconnects cleanly.
Zero persistent file writes, zero dataset admissions.
"""

import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = BASE_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from backend.app.services.real_csi_collector import RealCSICollector

def run_diagnostic(duration_sec: float = 10.0):
    print(f"=== Bounded Phase 52 CSI Stream Diagnostic ({duration_sec}s) ===")
    collector = RealCSICollector(
        port="COM5",
        baud_rate=115200,
        auto_connect=False,
        target_mac="98:BA:5F:EF:28:26",
        filter_by_mac=True
    )

    try:
        connected = collector.connect()
        if not connected:
            print("ERROR: Failed to connect to COM5.")
            return

        # Start background worker thread
        collector.start_streaming()
        print(f"Streaming started on COM5. Sampling for {duration_sec} seconds...")
        time.sleep(duration_sec)
        collector.stop_streaming()

        diag = collector.get_stream_diagnostics()
        health = collector.get_stream_health()

        print("\n=== Stream Diagnostic Telemetry ===")
        print(f"Diagnostic State:            {diag['diagnostic_state']}")
        print(f"Target MAC Filter:           {diag['target_mac']} (active: {diag['filter_by_mac']})")
        print(f"Admitted CSI Packets:        {diag['csi_packets_parsed']}")
        print(f"Filtered Non-Target Packets: {diag['filtered_non_target_packets']}")
        print(f"Packets Lost (Sequence):     {diag['packets_lost']}")
        print(f"Parser Errors:               {diag['parse_errors']}")
        print(f"Admitted Packet Rate:        {diag['packet_rate_hz']:.2f} Hz")
        print(f"Loss Percentage:             {health.get('loss_percentage', 0.0)}%")
        print(f"Total Serial Lines:          {health.get('total_lines_received', 0)}")
        print(f"Total Records Detected:      {health.get('total_records_detected', 0)}")
        print(f"Raw CSI Dimensions:          {diag['raw_csi_dimensions']}")
        print("Source MAC Distribution:")
        for mac, count in diag['source_mac_counts'].items():
            print(f"  - {mac}: {count} frames")

    finally:
        collector.disconnect()
        print(f"\nDisconnected. Port status: {'RELEASED' if collector.is_port_released() else 'HELD'}")

if __name__ == "__main__":
    run_diagnostic(10.0)
