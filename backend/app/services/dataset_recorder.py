import os
import csv
import time
import json
from typing import List, Dict, Any, Optional
from app.models.schemas import CSIPacketFrame

class DatasetRecorderService:
    """
    Dataset Capture & CSV/JSON Storage Engine.
    Records labeled CSI frames, subcarrier amplitudes/phases, ground truth (X, Y, Z) coordinates,
    semantic room zone, activity labels, and kinematic speed metrics for offline model training.
    """
    def __init__(self, data_dir: str = "data/recordings"):
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)
        self.is_recording = False
        self.current_session_id: Optional[str] = None
        self.current_label: str = "Walking"
    def get_recording_status(self) -> Dict[str, Any]:
        return {
            "is_recording": self.is_recording,
            "session_id": self.current_session_id,
            "label": self.current_label,
            "recorded_frames": len(self.recorded_frames),
            "recorded_frames_count": len(self.recorded_frames)
        }

    def start_recording(self, session_name: str = "", label: str = "Walking", subject_id: str = "Subject-01") -> Dict[str, Any]:
        self.is_recording = True
        self.current_label = label
        clean_name = session_name.replace(" ", "_") if session_name else f"csi_session_{int(time.time())}"
        self.current_session_id = clean_name
        self.recorded_frames = []
        return {
            "status": "started",
            "session_id": self.current_session_id,
            "id": self.current_session_id,
            "label": self.current_label
        }

    def record_frame(self, frame: CSIPacketFrame, target_x: float = 4.5, target_y: float = 3.5, target_z: float = 1.0, zone: str = "Workspace Area", speed: float = 0.0):
        if not self.is_recording:
            return

        record = {
            "session_id": self.current_session_id,
            "node_id": frame.node_id,
            "sequence": frame.sequence,
            "timestamp": frame.timestamp,
            "rssi": frame.rssi,
            "snr": frame.snr,
            "activity_label": self.current_label,
            "target_x": target_x,
            "target_y": target_y,
            "target_z": target_z,
            "zone": zone,
            "speed_ms": speed,
            "subcarriers_amp": frame.amplitudes,
            "subcarriers_phase": frame.phases
        }
        self.recorded_frames.append(record)

    def stop_recording(self) -> Dict[str, Any]:
        self.is_recording = False
        count = len(self.recorded_frames)
        session_id = self.current_session_id or f"csi_session_{int(time.time())}"

        json_path = os.path.join(self.data_dir, f"{session_id}.json")
        with open(json_path, "w") as f:
            json.dump(self.recorded_frames, f, indent=2)

        return {
            "status": "stopped",
            "session_id": session_id,
            "id": session_id,
            "frame_count": count,
            "label": self.current_label,
            "file_path": json_path
        }

    def export_csv(self, session_id: str) -> str:
        json_path = os.path.join(self.data_dir, f"{session_id}.json")
        csv_path = os.path.join(self.data_dir, f"{session_id}.csv")
        
        if not os.path.exists(json_path):
            raise FileNotFoundError(f"Session {session_id} not found.")

        with open(json_path, "r") as f:
            data = json.load(f)

        if not data:
            return ""

        with open(csv_path, "w", newline="") as f:
            writer = csv.writer(f)
            header = ["timestamp", "node_id", "sequence", "rssi", "snr", "activity_label", "target_x", "target_y", "target_z", "zone", "speed_ms"]
            header += [f"amp_{i}" for i in range(64)]
            header += [f"phase_{i}" for i in range(64)]
            writer.writerow(header)

            for item in data:
                row = [
                    item["timestamp"],
                    item["node_id"],
                    item["sequence"],
                    item["rssi"],
                    item["snr"],
                    item["activity_label"],
                    item["target_x"],
                    item["target_y"],
                    item["target_z"],
                    item["zone"],
                    item["speed_ms"]
                ]
                row.extend(item.get("subcarriers_amp", [0]*64))
                row.extend(item.get("subcarriers_phase", [0]*64))
                writer.writerow(row)

        with open(csv_path, "r") as f:
            return f.read()

dataset_recorder = DatasetRecorderService()
