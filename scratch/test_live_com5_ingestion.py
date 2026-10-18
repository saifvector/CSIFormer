import time
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR / "backend"))

from app.services.real_csi_collector import RealCSICollector
from app.services.live_pipeline_service import LivePipelineService

def main():
    svc = LivePipelineService()
    print("Starting real collector on COM5...")
    res = svc.start_collector(port="COM5", baud_rate=115200)
    print("Start result:", res)

    t0 = time.time()
    for _ in range(10):
        stats = svc.get_status()
        buffered = len(svc.collector.raw_frame_buffer) if svc.collector else 0
        pkts = stats.get("packets_received", 0)
        rate = stats.get("current_rate_hz", 0.0)
        print(f"Time: {time.time()-t0:.1f}s | Buffered: {buffered}/50 | Packets: {pkts} | Rate: {rate:.1f} Hz")
        if buffered >= 50:
            break
        time.sleep(0.5)

    pred = svc.predict_latest_window()
    print("Prediction result:", pred)
    stop_res = svc.stop_collector()
    print("Stop result:", stop_res)

if __name__ == "__main__":
    main()
