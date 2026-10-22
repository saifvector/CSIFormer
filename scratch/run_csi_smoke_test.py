import sys
import os
import time
import numpy as np

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.services.real_csi_collector import RealCSICollector

def run_csi_smoke_test(duration=8.0, port="COM5", baud_rate=115200):
    print(f"[CSI Smoke Test] Connecting to {port} at {baud_rate} baud...")
    collector = RealCSICollector(port=port, baud_rate=baud_rate, auto_connect=False)
    
    if not collector.connect(port=port, baud_rate=baud_rate):
        print(f"[CSI Smoke Test] ERROR: Failed to connect to {port}")
        return False

    print(f"[CSI Smoke Test] Starting acquisition for {duration} seconds...")
    collector.start_streaming()

    start_time = time.time()
    parsed_packets = []
    raw_lines = []
    parse_errors = 0

    try:
        while time.time() - start_time < duration:
            time.sleep(0.1)
    finally:
        collector.stop_streaming()
        collector.disconnect()

    elapsed = time.time() - start_time
    total_parsed = collector.csi_packets_parsed
    total_lines = collector.total_lines_received
    total_bytes = collector.total_bytes_received
    errors = collector.parse_errors
    packet_rate = (total_parsed / elapsed) if elapsed > 0 else 0.0

    print("\n" + "=" * 60)
    print("           PHASE 50 CSI HARDWARE SMOKE TEST REPORT")
    print("=" * 60)
    print(f"Target Port          : {port}")
    print(f"Baud Rate            : {baud_rate}")
    print(f"Elapsed Duration     : {elapsed:.2f} seconds")
    print(f"Total Bytes Received : {total_bytes} bytes")
    print(f"Total Lines Received : {total_lines}")
    print(f"CSI Packets Parsed   : {total_parsed}")
    print(f"Parse Errors         : {errors}")
    print(f"Average Packet Rate  : {packet_rate:.2f} Hz")
    print(f"Last RSSI            : {collector.current_rssi} dBm")
    print(f"Last Noise Floor     : {collector.current_noise} dBm")
    print(f"Raw CSI Dimensions   : {collector.raw_csi_dimensions} subcarriers")
    print(f"Diagnostic State     : {collector.diagnostic_state}")
    print(f"Port Released Cleanly: {collector.is_port_released()}")
    print("=" * 60)

    # Check validation criteria
    success = (total_parsed >= 5) and (errors == 0) and (collector.raw_csi_dimensions in [56, 64])
    print(f"Smoke Test Disposition: {'PASS' if success else 'FAIL'}")
    return success

if __name__ == "__main__":
    run_csi_smoke_test(duration=8.0, port="COM5", baud_rate=115200)
