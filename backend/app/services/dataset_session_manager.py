import os
import csv
import json
import time
import math
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from app.models.schemas import CSIPacketFrame
from app.services.packet_validator import packet_validator
from app.services.data_quality_analyzer import data_quality_analyzer, DataQualityReport

CLASS_FOLDER_MAP = {
    "Empty Room": "empty_room",
    "Standing": "standing",
    "Sitting": "sitting",
    "Walking": "walking",
    "Running": "running",
    "Falling": "falling",
    "Lying Down": "lying_down",
    "Multiple Persons": "multiperson",
}

FOLDER_CLASS_MAP = {v: k for k, v in CLASS_FOLDER_MAP.items()}

class DatasetSessionManager:
    """
    Centralized Real-World Wi-Fi CSI Dataset Acquisition & Session Lifecycle Engine.
    Manages:
    - Centralized dataset directory structure
    - Recording session lifecycle (Start, Pause, Resume, Stop, Cancel)
    - Multi-format file serialization (CSV, JSON, NumPy NPY)
    - Metadata tracking & session manifest generation
    - Real-time disk analytics & programmatic research-readiness reporting
    """
    def __init__(self, root_dataset_dir: str = "dataset"):
        self.root_dir = root_dataset_dir
        self.is_recording = False
        self.is_paused = False
        
        # Session State
        self.session_id: Optional[str] = None
        self.activity_class: str = "Walking"
        self.subject_id: str = "Subject-01"
        self.room_name: str = "Defense Lab 101"
        self.room_size: str = "10.0m x 8.0m x 3.5m"
        self.router_id: str = "Router-TX-01"
        self.router_location: str = "X: 8.2m, Y: 1.5m, Z: 0.82m"
        self.esp32_nodes: List[str] = ["esp32-rx-01", "esp32-rx-02", "esp32-rx-03"]
        self.experiment_id: str = "EXP-CSI-001"
        self.notes: str = ""
        
        self.start_time: float = 0.0
        self.pause_start_time: float = 0.0
        self.total_paused_duration: float = 0.0
        
        self.recorded_frames: List[Dict[str, Any]] = []
        self.init_directories()

    def init_directories(self):
        """Initializes full dataset storage hierarchy if folders do not exist."""
        subfolders = list(CLASS_FOLDER_MAP.values()) + ["metadata", "sessions", "exports", "reports"]
        for sub in subfolders:
            path = os.path.join(self.root_dir, sub)
            os.makedirs(path, exist_ok=True)

    def start_session(
        self,
        activity_class: str = "Walking",
        subject_id: str = "Subject-01",
        room_name: str = "Defense Lab 101",
        room_size: str = "10.0m x 8.0m x 3.5m",
        router_id: str = "Router-TX-01",
        router_location: str = "X: 8.2m, Y: 1.5m, Z: 0.82m",
        esp32_nodes: Optional[List[str]] = None,
        experiment_id: str = "EXP-CSI-001",
        notes: str = "",
        custom_session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Starts a fresh dataset acquisition recording session."""
        self.init_directories()
        self.is_recording = True
        self.is_paused = False
        
        self.activity_class = activity_class if activity_class in CLASS_FOLDER_MAP else "Walking"
        self.subject_id = subject_id.strip() or "Subject-01"
        self.room_name = room_name.strip() or "Defense Lab 101"
        self.room_size = room_size.strip() or "10.0m x 8.0m x 3.5m"
        self.router_id = router_id.strip() or "Router-TX-01"
        self.router_location = router_location.strip() or "X: 8.2m, Y: 1.5m, Z: 0.82m"
        self.esp32_nodes = esp32_nodes or ["esp32-rx-01", "esp32-rx-02", "esp32-rx-03"]
        self.experiment_id = experiment_id.strip() or "EXP-CSI-001"
        self.notes = notes.strip()

        now = time.time()
        self.start_time = now
        self.total_paused_duration = 0.0
        self.recorded_frames = []

        class_slug = CLASS_FOLDER_MAP.get(self.activity_class, "walking")
        clean_subj = self.subject_id.replace(" ", "_")
        if custom_session_id:
            self.session_id = custom_session_id.replace(" ", "_")
        else:
            self.session_id = f"CSI_SES_{class_slug}_{clean_subj}_{int(now)}"

        # Reset packet validator and quality analyzer
        packet_validator.reset_node_state()
        data_quality_analyzer.start_session_monitoring(self.session_id, now)

        return {
            "status": "started",
            "session_id": self.session_id,
            "activity_class": self.activity_class,
            "subject_id": self.subject_id,
            "start_time": self.start_time,
            "room_name": self.room_name,
            "monitored_nodes": self.esp32_nodes
        }

    def pause_session(self) -> Dict[str, Any]:
        """Pauses in-flight packet recording."""
        if not self.is_recording or self.is_paused:
            return {"status": "not_active_or_already_paused"}
        
        self.is_paused = True
        self.pause_start_time = time.time()
        return {"status": "paused", "session_id": self.session_id}

    def resume_session(self) -> Dict[str, Any]:
        """Resumes paused packet recording."""
        if not self.is_recording or not self.is_paused:
            return {"status": "not_paused"}
        
        paused_dt = time.time() - self.pause_start_time
        self.total_paused_duration += max(0.0, paused_dt)
        self.is_paused = False
        return {"status": "resumed", "session_id": self.session_id}

    def cancel_session(self) -> Dict[str, Any]:
        """Cancels and discards active recording without saving to disk."""
        if not self.is_recording:
            return {"status": "no_active_session"}
        
        sid = self.session_id
        self.is_recording = False
        self.is_paused = False
        self.recorded_frames = []
        self.session_id = None
        data_quality_analyzer.reset_session_buffers()
        return {"status": "cancelled", "session_id": sid}

    def record_frame(
        self,
        frame: CSIPacketFrame,
        target_x: float = 4.5,
        target_y: float = 3.5,
        target_z: float = 1.0,
        zone: str = "Workspace Area",
        speed_ms: float = 0.0
    ):
        """Validates and buffers an incoming CSI subcarrier packet during active recording."""
        if not self.is_recording or self.is_paused:
            return

        # 1. Validate packet
        val_result = packet_validator.validate_frame(frame)
        
        # 2. Feed metrics to DataQualityAnalyzer
        data_quality_analyzer.process_frame_metrics(frame, val_result)

        if not val_result.is_valid:
            return # Discard severely malformed frames from dataset payload

        # 3. Buffer structured record
        record = {
            "session_id": self.session_id,
            "node_id": frame.node_id,
            "sequence": frame.sequence,
            "timestamp": frame.timestamp,
            "rssi": frame.rssi,
            "snr": frame.snr,
            "activity_label": self.activity_class,
            "subject_id": self.subject_id,
            "target_x": round(target_x, 3),
            "target_y": round(target_y, 3),
            "target_z": round(target_z, 3),
            "zone": zone,
            "speed_ms": round(speed_ms, 2),
            "subcarriers_amp": frame.amplitudes,
            "subcarriers_phase": frame.phases
        }
        self.recorded_frames.append(record)

    def stop_session(self) -> Dict[str, Any]:
        """
        Finalizes active recording, evaluates data quality, and serializes dataset artifacts
        into CSV, JSON, and NumPy NPY binary files.
        """
        if not self.is_recording:
            return {"status": "no_active_session"}

        now = time.time()
        end_time = now
        total_duration = max(0.1, round(end_time - self.start_time - self.total_paused_duration, 2))
        
        sid = self.session_id or f"CSI_SES_{int(now)}"
        class_folder = CLASS_FOLDER_MAP.get(self.activity_class, "walking")
        class_dir = os.path.join(self.root_dir, class_folder)
        os.makedirs(class_dir, exist_ok=True)

        # 1. Compute Quality Report
        quality_report = data_quality_analyzer.compute_quality_report(sid)

        # 2. Construct Full Metadata Manifest
        metadata = {
            "session_id": sid,
            "activity_class": self.activity_class,
            "class_slug": class_folder,
            "subject_id": self.subject_id,
            "experiment_id": self.experiment_id,
            "room_name": self.room_name,
            "room_size": self.room_size,
            "router_id": self.router_id,
            "router_location": self.router_location,
            "esp32_nodes": self.esp32_nodes,
            "notes": self.notes,
            "start_time": self.start_time,
            "end_time": end_time,
            "duration_seconds": total_duration,
            "frame_count": len(self.recorded_frames),
            "quality": quality_report.to_dict(),
            "exported_files": {
                "json": f"{class_folder}/{sid}.json",
                "csv": f"{class_folder}/{sid}.csv",
                "npy": f"{class_folder}/{sid}.npy"
            }
        }

        # 3. Serialize JSON Artifacts
        json_class_path = os.path.join(class_dir, f"{sid}.json")
        json_sessions_path = os.path.join(self.root_dir, "sessions", f"{sid}.json")
        json_meta_path = os.path.join(self.root_dir, "metadata", f"{sid}.json")
        json_report_path = os.path.join(self.root_dir, "reports", f"quality_{sid}.json")

        with open(json_class_path, "w") as f:
            json.dump(self.recorded_frames, f, indent=2)

        with open(json_sessions_path, "w") as f:
            json.dump({"metadata": metadata, "frames": self.recorded_frames}, f, indent=2)

        with open(json_meta_path, "w") as f:
            json.dump(metadata, f, indent=2)

        with open(json_report_path, "w") as f:
            json.dump(quality_report.to_dict(), f, indent=2)

        # 4. Serialize CSV Tabular File
        csv_class_path = os.path.join(class_dir, f"{sid}.csv")
        csv_exports_path = os.path.join(self.root_dir, "exports", f"{sid}.csv")

        self._write_csv(csv_class_path)
        self._write_csv(csv_exports_path)

        # 5. Serialize NumPy .npy 3D Tensor for PyTorch DataLoader
        npy_class_path = os.path.join(class_dir, f"{sid}.npy")
        self._write_npy(npy_class_path)

        self.is_recording = False
        self.is_paused = False
        self.session_id = None

        return {
            "status": "completed",
            "session_id": sid,
            "activity_class": self.activity_class,
            "subject_id": self.subject_id,
            "duration_seconds": total_duration,
            "frame_count": len(self.recorded_frames),
            "quality_level": quality_report.quality_level,
            "composite_quality_score": quality_report.composite_quality_score,
            "files": {
                "json": json_class_path,
                "csv": csv_class_path,
                "npy": npy_class_path,
                "metadata": json_meta_path
            }
        }

    def _write_csv(self, filepath: str):
        """Writes buffered frames to CSV."""
        with open(filepath, "w", newline="") as f:
            writer = csv.writer(f)
            header = [
                "timestamp", "node_id", "sequence", "rssi", "snr",
                "activity_label", "subject_id", "target_x", "target_y", "target_z",
                "zone", "speed_ms"
            ]
            header += [f"amp_{i}" for i in range(64)]
            header += [f"phase_{i}" for i in range(64)]
            writer.writerow(header)

            for item in self.recorded_frames:
                row = [
                    item["timestamp"],
                    item["node_id"],
                    item["sequence"],
                    item["rssi"],
                    item["snr"],
                    item["activity_label"],
                    item["subject_id"],
                    item["target_x"],
                    item["target_y"],
                    item["target_z"],
                    item["zone"],
                    item["speed_ms"]
                ]
                row.extend(item.get("subcarriers_amp", [0.0]*64))
                row.extend(item.get("subcarriers_phase", [0.0]*64))
                writer.writerow(row)

    def _write_npy(self, filepath: str):
        """
        Serializes raw CSI frames into structured NumPy array.
        Tensor Shape: [Num_Frames, 64_Subcarriers, 2] (Channels: 0=Amplitude, 1=Phase).
        """
        if not self.recorded_frames:
            np.save(filepath, np.zeros((0, 64, 2), dtype=np.float32))
            return

        tensor_list = []
        for item in self.recorded_frames:
            amps = item.get("subcarriers_amp", [0.0]*64)
            phases = item.get("subcarriers_phase", [0.0]*64)
            frame_arr = np.stack([amps, phases], axis=-1) # Shape [64, 2]
            tensor_list.append(frame_arr)

        full_tensor = np.array(tensor_list, dtype=np.float32) # Shape [N, 64, 2]
        np.save(filepath, full_tensor)

    def get_live_status(self) -> Dict[str, Any]:
        """Returns live recording status for HUD telemetry."""
        now = time.time()
        elapsed = 0.0
        if self.is_recording and self.start_time > 0:
            elapsed = round(now - self.start_time - self.total_paused_duration, 1)

        quality_report = data_quality_analyzer.compute_quality_report(self.session_id or "LIVE")
        
        return {
            "is_recording": self.is_recording,
            "is_paused": self.is_paused,
            "session_id": self.session_id,
            "activity_class": self.activity_class,
            "subject_id": self.subject_id,
            "room_name": self.room_name,
            "elapsed_seconds": elapsed,
            "recorded_frames": len(self.recorded_frames),
            "packet_loss_pct": quality_report.packet_loss_pct,
            "quality_level": quality_report.quality_level,
            "composite_quality_score": quality_report.composite_quality_score,
            "avg_snr": quality_report.avg_snr,
            "avg_rssi": quality_report.avg_rssi
        }

    def get_dataset_statistics(self) -> Dict[str, Any]:
        """
        Scans physical dataset/ directory on disk and computes real empirical metrics:
        - Class distribution & frame counts
        - Total subjects & recordings
        - Storage size in bytes
        - Class balance score & status badge
        """
        self.init_directories()
        
        class_stats: Dict[str, Dict[str, Any]] = {}
        total_recordings = 0
        total_frames = 0
        total_bytes = 0
        subjects_set = set()
        total_duration_sec = 0.0

        for class_label, folder in CLASS_FOLDER_MAP.items():
            class_path = os.path.join(self.root_dir, folder)
            json_files = [f for f in os.listdir(class_path) if f.endswith(".json")] if os.path.exists(class_path) else []
            
            c_frames = 0
            c_bytes = 0
            c_duration = 0.0

            for jf in json_files:
                fpath = os.path.join(class_path, jf)
                c_bytes += os.path.getsize(fpath)
                
                # Check associated CSV / NPY
                csv_path = fpath.replace(".json", ".csv")
                npy_path = fpath.replace(".json", ".npy")
                if os.path.exists(csv_path):
                    c_bytes += os.path.getsize(csv_path)
                if os.path.exists(npy_path):
                    c_bytes += os.path.getsize(npy_path)

                try:
                    with open(fpath, "r") as fp:
                        data = json.load(fp)
                        if isinstance(data, list):
                            c_frames += len(data)
                            for frame in data:
                                if "subject_id" in frame:
                                    subjects_set.add(frame["subject_id"])
                except Exception:
                    pass

            # Check metadata files for duration
            meta_path = os.path.join(self.root_dir, "metadata")
            if os.path.exists(meta_path):
                for mf in os.listdir(meta_path):
                    if mf.endswith(".json") and folder in mf:
                        try:
                            with open(os.path.join(meta_path, mf), "r") as mfp:
                                mdata = json.load(mfp)
                                c_duration += mdata.get("duration_seconds", 0.0)
                        except Exception:
                            pass

            total_recordings += len(json_files)
            total_frames += c_frames
            total_bytes += c_bytes
            total_duration_sec += c_duration

            class_stats[class_label] = {
                "folder": folder,
                "recordings_count": len(json_files),
                "frames_count": c_frames,
                "storage_bytes": c_bytes,
                "duration_seconds": round(c_duration, 1)
            }

        # Compute Class Balance Score (0.0 to 100.0%)
        counts = [cs["recordings_count"] for cs in class_stats.values()]
        total_c = sum(counts)
        num_classes = len(CLASS_FOLDER_MAP)
        
        if total_c == 0:
            balance_score = 0.0
            status_indicator = "NEEDS MORE DATA"
        else:
            # Normalized Shannon Entropy
            probs = [c / total_c for c in counts if c > 0]
            entropy = -sum(p * math.log(p) for p in probs)
            max_entropy = math.log(num_classes)
            balance_score = round((entropy / max_entropy) * 100.0, 1) if max_entropy > 0 else 100.0
            
            missing_count = sum(1 for c in counts if c == 0)
            if missing_count > 0 or total_recordings < 8:
                status_indicator = "NEEDS MORE DATA"
            elif balance_score < 60.0:
                status_indicator = "CLASS IMBALANCE DETECTED"
            else:
                status_indicator = "HEALTHY"

        missing_classes = [cls for cls, cs in class_stats.items() if cs["recordings_count"] == 0]

        return {
            "dataset_root": self.root_dir,
            "total_recordings": total_recordings,
            "total_frames": total_frames,
            "total_subjects": max(1, len(subjects_set)) if total_recordings > 0 else 0,
            "total_duration_seconds": round(total_duration_sec, 1),
            "total_storage_bytes": total_bytes,
            "storage_mb": round(total_bytes / (1024 * 1024), 2),
            "class_balance_score_pct": balance_score,
            "status_indicator": status_indicator,
            "missing_classes": missing_classes,
            "class_distribution": class_stats
        }

    def generate_research_readiness_report(self) -> Dict[str, Any]:
        """
        Generates programmatic, evidence-based research readiness report.
        """
        stats = self.get_dataset_statistics()
        
        missing = stats["missing_classes"]
        total_rec = stats["total_recordings"]
        balance = stats["class_balance_score_pct"]

        recommendations = []
        if missing:
            recommendations.append(f"Execute recording protocols for missing classes: {', '.join(missing)}.")
        if stats["total_subjects"] < 5:
            recommendations.append(f"Expand participant cohort (currently {stats['total_subjects']} subjects; target >= 5 subjects).")
        if stats["total_frames"] < 5000:
            recommendations.append("Collect additional continuous 30 Hz timeseries sessions to reach >= 5,000 training frames.")
        if balance < 75.0 and total_rec > 0:
            recommendations.append(f"Rebalance dataset distribution (current balance {balance}% is below research threshold 75%).")
        if not recommendations:
            recommendations.append("Dataset satisfies research-grade criteria for PyTorch transformer retraining.")

        # Readiness Level
        if total_rec >= 16 and not missing and balance >= 75.0:
            readiness_level = "PRODUCTION_RESEARCH_READY"
            readiness_pct = 95.0
        elif total_rec >= 8 and len(missing) <= 2:
            readiness_level = "PRELIMINARY_TRAINING_READY"
            readiness_pct = 70.0
        elif total_rec > 0:
            readiness_level = "COLLECTION_IN_PROGRESS"
            readiness_pct = 40.0
        else:
            readiness_level = "INFRASTRUCTURE_DEPLOYED_NO_DATA"
            readiness_pct = 20.0

        return {
            "readiness_level": readiness_level,
            "readiness_score_pct": readiness_pct,
            "dataset_statistics": stats,
            "missing_categories_count": len(missing),
            "recommendations": recommendations,
            "generated_timestamp": time.time()
        }

dataset_session_manager = DatasetSessionManager()
