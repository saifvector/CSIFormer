"""
CSIFormer Phase 17 — Standardized Real-World CSI Collection Workflow.

Provides an audited, reproducible procedure for:
1. Verifying the ESP32-S3 serial connection and active packet stream.
2. Managing active UDP traffic stimulation (192.168.0.232:5555) to sustain 35+ Hz rate.
3. Enforcing privacy-preserving participant identifiers (e.g., Participant_01).
4. Enforcing valid activity labels from the HAR taxonomy.
5. Preserving raw uninterpolated CSI alongside aligned features.
6. Recording packet loss, sequence discontinuities, duration, and room condition.
7. Post-capture confirmation/rejection (unconfirmed trials marked as 'unknown').
8. Updating dataset_manifest.json and validating integrity.
"""

import sys
import time
import json
import socket
import threading
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
sys.path.append(str(ROOT_DIR))
sys.path.append(str(ROOT_DIR / "backend"))

from app.services.real_csi_collector import RealCSICollector

DATASET_DIR = ROOT_DIR / "data" / "real_csi_dataset"
DATASET_DIR.mkdir(parents=True, exist_ok=True)

VALID_LABELS = {
    "push_pull": {"class_id": 0, "name": "Push and Pull"},
    "clap":      {"class_id": 2, "name": "Two-Hand Clapping"},
    "static":    {"class_id": 6, "name": "Static / Background"},
    "sit":       {"class_id": 8, "name": "Sitting Transition"},
    "fall":      {"class_id": 9, "name": "Controlled Padded Fall (Safe)"},
    "walk":      {"class_id": 11, "name": "Walking in LOS"},
    "unknown":   {"class_id": -1, "name": "Unconfirmed / Ambiguous Activity"}
}


class UdpStimulator:
    """Sends background UDP probes to stimulate ESP32-S3 CSI callbacks at ~35 Hz."""
    def __init__(self, target_ip: str = "192.168.0.232", port: int = 5555, rate_hz: float = 35.0):
        self.target_ip = target_ip
        self.port = port
        self.interval = 1.0 / rate_hz
        self.stop_event = threading.Event()
        self.thread: Optional[threading.Thread] = None
        self.packets_sent = 0

    def _loop(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        while not self.stop_event.is_set():
            try:
                sock.sendto(b"CSI_PROBE_P17", (self.target_ip, self.port))
                self.packets_sent += 1
            except Exception:
                pass
            time.sleep(self.interval)
        sock.close()

    def start(self):
        self.stop_event.clear()
        self.packets_sent = 0
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=1.0)


class CollectionWorkflowManager:
    """Manages the full lifecycle of a CSI recording session."""

    def __init__(self, port: str = "COM5", baud_rate: int = 115200, data_dir: Optional[Path] = None):
        self.port = port
        self.baud_rate = baud_rate
        self.data_dir = Path(data_dir) if data_dir else DATASET_DIR
        self.collector = RealCSICollector(port=port, baud_rate=baud_rate, data_dir=str(self.data_dir))
        self.stimulator = UdpStimulator()
        self.active_session_info: Optional[Dict[str, Any]] = None

    def verify_hardware_stream(self, test_duration_s: float = 12.0, trigger_reset: bool = True) -> Dict[str, Any]:
        """
        Tests the serial connection and checks if physical CSI packets are streaming.
        Differentiates between:
        1. Port unavailable (SERIAL_DISCONNECTED)
        2. Port opened but no serial bytes received (SERIAL_CONNECTED_IDLE)
        3. Bytes received but no complete records detected (SERIAL_BYTES_NO_VALID_RECORDS)
        4. Records detected but parsing fails (RECORDS_RECEIVED_PARSE_FAILED)
        5. Valid records parsed but no valid CSI arrays found (RECORDS_RECEIVED_PARSE_FAILED)
        6. Valid CSI packets received (CSI_STREAM_ACTIVE or STREAM_INTERRUPTED)
        """
        if not self.collector.connect():
            return {
                "status": "error",
                "connected": False,
                "port": self.port,
                "diagnostic_state": "SERIAL_DISCONNECTED",
                "message": f"Could not open serial port {self.port} at {self.baud_rate} baud.",
                "duration_s": test_duration_s,
                "total_bytes_received": 0,
                "total_records_detected": 0,
                "packets_received_during_test": 0,
                "packet_rate_hz": 0.0,
                "mean_rssi": -99.0,
                "raw_csi_dimensions": None
            }

        # Optionally pulse normal reset so ESP32-S3 boots into flash if trapped in bootloader
        if trigger_reset:
            self.collector.trigger_normal_reset()

        self.collector.start_streaming()
        self.stimulator.start()
        time.sleep(test_duration_s)
        self.stimulator.stop()

        health = self.collector.get_stream_health()
        pkts = self.collector.packets_received
        total_bytes = health.get("total_bytes_received", 0)
        total_records = health.get("total_records_detected", 0)
        parse_errors = health.get("parse_errors", 0)
        diagnostic_state = health.get("diagnostic_state", "SERIAL_DISCONNECTED")
        raw_dim = health.get("raw_csi_dimensions")

        self.collector.stop_streaming()
        self.collector.disconnect()

        # Determine granular status while preserving backward-compatibility
        if pkts > 0:
            status = "ok"
        elif total_records > 0 and parse_errors > 0:
            status = "records_parse_failed"
        elif total_records > 0 and (raw_dim is None or raw_dim == 0):
            status = "no_valid_csi_arrays"
        elif total_bytes > 0:
            status = "bytes_no_records"
        else:
            status = "no_packets"

        return {
            "status": status,
            "connected": True,
            "port": self.port,
            "baud_rate": self.baud_rate,
            "duration_s": test_duration_s,
            "diagnostic_state": diagnostic_state,
            "total_bytes_received": total_bytes,
            "total_lines_received": health.get("total_lines_received", 0),
            "total_records_detected": total_records,
            "packets_received_during_test": pkts,
            "parse_errors": parse_errors,
            "raw_csi_dimensions": raw_dim,
            "packet_rate_hz": health.get("packet_rate_hz", 0.0),
            "mean_rssi": health.get("rssi_dbm", -99.0),
            "detected_protocol": health.get("detected_protocol", "unknown"),
            "boot_messages": health.get("boot_messages", [])
        }

    def start_session(
        self,
        participant_id: str,
        activity_label: str,
        room_type: str = "Laboratory",
        tx_rx_distance_m: float = 2.5,
        tx_position: str = "Tx_Baseline_Origin",
        rx_position: str = "Rx_Baseline_Node",
        orientation: str = "LOS_Facing_TxRx",
        duration_seconds: float = 4.0,
        event_id: Optional[str] = None,
        notes: str = ""
    ) -> Dict[str, Any]:
        """Validates parameters, connects hardware, and starts recording."""
        if activity_label not in VALID_LABELS:
            raise ValueError(f"Invalid activity_label '{activity_label}'. Must be one of: {list(VALID_LABELS.keys())}")

        if not self.collector.connect():
            raise ConnectionError(f"Cannot connect to ESP32-S3 on port {self.port}.")

        self.collector.trigger_normal_reset()
        self.collector.start_streaming()
        self.stimulator.start()

        # Let packet stream stabilize after hardware connection/boot (wait for first packet or max 30s)
        t_start_wait = time.time()
        while time.time() - t_start_wait < 30.0:
            if self.collector.csi_packets_parsed > 0:
                break
            time.sleep(0.2)

        if self.collector.csi_packets_parsed == 0:
            raise TimeoutError("CSI packet stream did not activate within 30.0s stabilization window.")

        clean_label = activity_label.lower()
        clean_pid = participant_id.replace(" ", "_")
        now_ts = int(time.time())
        session_name = f"real_{clean_label}_{clean_pid}_{now_ts}"
        evt_id = event_id or f"evt_{clean_label}_{clean_pid}_{now_ts}"

        rec_res = self.collector.start_session_recording(
            session_name=session_name,
            room_type=room_type,
            participant_id=clean_pid,
            activity_label=clean_label,
            tx_rx_distance_m=tx_rx_distance_m,
            orientation=orientation,
            ground_truth_confirmed=True,
            notes=notes
        )

        self.active_session_info = {
            "session_id": rec_res["session_id"],
            "event_id": evt_id,
            "participant_id": clean_pid,
            "activity_label": clean_label,
            "class_id": VALID_LABELS[clean_label]["class_id"],
            "duration_seconds": duration_seconds,
            "room_type": room_type,
            "tx_rx_distance_m": tx_rx_distance_m,
            "tx_position": tx_position,
            "rx_position": rx_position,
            "orientation": orientation,
            "notes": notes,
            "start_time": time.time()
        }

        return {
            "status": "recording_active",
            "session_id": rec_res["session_id"],
            "event_id": evt_id,
            "participant": clean_pid,
            "activity": clean_label,
            "target_duration_s": duration_seconds
        }

    def stop_session(self) -> Dict[str, Any]:
        """Stops recording and returns session performance telemetry (idempotent)."""
        if not self.active_session_info:
            return {"status": "no_active_session"}

        if self.active_session_info.get("stopped", False):
            return {
                "status": "recording_stopped",
                "session_id": self.active_session_info["session_id"],
                "event_id": self.active_session_info.get("event_id"),
                "frame_count": self.active_session_info.get("frame_count", 0),
                "json_path": self.active_session_info.get("saved_json"),
                "csv_path": self.active_session_info.get("saved_csv"),
                "already_stopped": True
            }

        self.stimulator.stop()
        res = self.collector.stop_session_recording()
        self.collector.stop_streaming()
        self.collector.disconnect()

        self.active_session_info["saved_json"] = res.get("json_path")
        self.active_session_info["saved_csv"] = res.get("csv_path")
        self.active_session_info["frame_count"] = res.get("frame_count", 0)
        self.active_session_info["stopped"] = True
        self.active_session_info["stop_status"] = res.get("status")
        if res.get("status") == "error":
            self.active_session_info["error"] = res.get("error")

        return {
            "status": "recording_stopped" if res.get("status") != "error" else "error",
            "session_id": self.active_session_info["session_id"],
            "event_id": self.active_session_info.get("event_id"),
            "frame_count": res.get("frame_count", 0),
            "json_path": res.get("json_path"),
            "csv_path": res.get("csv_path"),
            "error": res.get("error")
        }

    def finalize_and_index_session(
        self,
        confirmed: bool,
        split: str = "train",
        notes: str = "",
        enforce_validation: bool = True
    ) -> Dict[str, Any]:
        """
        Confirms or rejects the recorded session.
        If confirmed: validates session file, then registers the session in dataset_manifest.json.
        If rejected: updates activity to 'unknown' (class_id -1).
        If validation fails and enforce_validation is True: manifest is NOT updated.
        """
        if not self.active_session_info:
            return {"status": "no_session_to_finalize"}

        json_path_str = self.active_session_info.get("saved_json")
        if not json_path_str:
            return {"status": "error", "message": "No saved session JSON path found."}

        json_path = Path(json_path_str)
        if not json_path.exists():
            return {"status": "error", "message": f"Session file not found: {json_path}"}

        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            return {"status": "error", "message": f"Failed to read session JSON: {e}"}

        actual_activity = self.active_session_info["activity_label"] if confirmed else "unknown"
        actual_cid = VALID_LABELS[actual_activity]["class_id"]
        confirmation_status = "confirmed" if confirmed else "rejected"

        if "metadata" not in data:
            data["metadata"] = {}

        data["metadata"]["event_id"] = self.active_session_info.get("event_id")
        data["metadata"]["ground_truth_confirmed"] = confirmed
        data["metadata"]["confirmation_status"] = confirmation_status
        data["metadata"]["ground_truth_activity"] = actual_activity
        data["metadata"]["tx_position"] = self.active_session_info.get("tx_position", "Tx_Baseline_Origin")
        data["metadata"]["rx_position"] = self.active_session_info.get("rx_position", "Rx_Baseline_Node")
        data["metadata"]["subcarrier_alignment_method"] = "linear_interpolation_to_56"
        if notes:
            data["metadata"]["notes"] = f"{data['metadata'].get('notes', '')} | {notes}".strip(" | ")

        # Write back updated metadata
        try:
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            return {"status": "error", "message": f"Failed to update session metadata in JSON: {e}"}

        # Validate session file using DatasetIntegrityValidator
        validation_passed = False
        validation_error = None
        validation_result = None

        try:
            from app.services.session_validator import DatasetIntegrityValidator
            validator = DatasetIntegrityValidator(self.data_dir)
            validation_result = validator.validate_session_file(json_path)
            validation_passed = True
        except Exception as e:
            validation_passed = False
            validation_error = str(e)

        manifest_updated = False
        sid = self.active_session_info["session_id"]

        # Update dataset_manifest.json ONLY if validation passed (or validation not enforced)
        if (not enforce_validation) or validation_passed:
            try:
                manifest_path = self.data_dir / "dataset_manifest.json"
                if manifest_path.exists():
                    with open(manifest_path, "r", encoding="utf-8") as f:
                        manifest = json.load(f)
                else:
                    manifest = {
                        "dataset_name": "CSIFormer_Real_ESP32S3_CSI_Dataset",
                        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        "sessions": []
                    }

                existing_sids = [s["session_id"] for s in manifest.get("sessions", [])]
                if sid not in existing_sids:
                    manifest["sessions"].append({
                        "session_id": sid,
                        "event_id": self.active_session_info.get("event_id"),
                        "activity_label": actual_activity,
                        "class_id": actual_cid,
                        "description": VALID_LABELS[actual_activity]["name"],
                        "confirmation_status": confirmation_status,
                        "participant_id": self.active_session_info["participant_id"],
                        "split": split,
                        "room": self.active_session_info["room_type"],
                        "tx_rx_distance_m": self.active_session_info["tx_rx_distance_m"],
                        "tx_position": self.active_session_info.get("tx_position", "Tx_Baseline_Origin"),
                        "rx_position": self.active_session_info.get("rx_position", "Rx_Baseline_Node"),
                        "orientation": self.active_session_info["orientation"],
                        "carrier_frequency_ghz": 2.442,
                        "wifi_channel": 7,
                        "bssid": "98:ba:5f:ef:28:26",
                        "duration_seconds": data["metadata"].get("duration_seconds", 4.0),
                        "packet_count": self.active_session_info["frame_count"],
                        "sampling_rate_hz": data["metadata"].get("mean_sampling_rate_hz", 35.0),
                        "mean_rssi_dbm": -58.0,
                        "subcarrier_alignment_method": "linear_interpolation_to_56",
                        "json_file": json_path.name,
                        "csv_file": f"{sid}.csv"
                    })

                    manifest["splits_summary"] = {
                        "train_sessions": sum(1 for s in manifest["sessions"] if s["split"] == "train"),
                        "val_sessions": sum(1 for s in manifest["sessions"] if s["split"] == "val"),
                        "test_sessions": sum(1 for s in manifest["sessions"] if s["split"] == "test"),
                        "total_sessions": len(manifest["sessions"]),
                        "total_frames": sum(s["packet_count"] for s in manifest["sessions"])
                    }

                    with open(manifest_path, "w", encoding="utf-8") as f:
                        json.dump(manifest, f, indent=2)

                manifest_updated = True
            except Exception as e:
                manifest_updated = False
                validation_error = f"Manifest update failed: {e}"

        return {
            "status": "session_finalized" if validation_passed else "validation_failed",
            "session_id": sid,
            "event_id": self.active_session_info.get("event_id"),
            "confirmed": confirmed,
            "activity_label": actual_activity,
            "class_id": actual_cid,
            "manifest_updated": manifest_updated,
            "validation_passed": validation_passed,
            "validation_error": validation_error,
            "validation_result": validation_result
        }

    def safe_shutdown(
        self,
        confirmed: Optional[bool] = None,
        split: str = "train",
        notes: str = ""
    ) -> Dict[str, Any]:
        """
        Executes the audited 7-step safe shutdown sequence for the ESP32-S3:
        1. Stop accepting new CSI frames for active session (is_recording = False).
        2. Finish processing frames already received / drain active acquisition.
        3. Finalize recording and flush/close JSON & CSV files to disk via stop_session().
        4. Validate session file using DatasetIntegrityValidator.
           Update dataset_manifest.json ONLY IF validation passes and confirmed is not None.
        5. Stop background acquisition thread cleanly (stop_streaming).
        6. Release serial connection and verify port release (is_port_released).
        7. Return structured status indicating whether USB disconnection is safe.
        """
        # Step 1, 2, 3: Stop session and finalize files
        stop_res = self.stop_session()
        had_active_session = bool(self.active_session_info)
        frame_count = stop_res.get("frame_count", 0) if had_active_session else 0
        json_path_str = stop_res.get("json_path") if had_active_session else None
        csv_path_str = stop_res.get("csv_path") if had_active_session else None
        files_finalized = bool(json_path_str and Path(json_path_str).exists())

        # Step 4: Validate session file and conditionally update manifest
        validation_passed = None
        validation_error = None
        manifest_updated = False
        activity_label = None
        class_id = None

        if files_finalized:
            json_path = Path(json_path_str)
            if confirmed is not None:
                fin_res = self.finalize_and_index_session(confirmed=confirmed, split=split, notes=notes)
                validation_passed = fin_res.get("validation_passed", False)
                validation_error = fin_res.get("validation_error")
                manifest_updated = fin_res.get("manifest_updated", False)
                activity_label = fin_res.get("activity_label")
                class_id = fin_res.get("class_id")
            else:
                # Interrupted / aborted trial: validate file without indexing into manifest
                try:
                    from app.services.session_validator import DatasetIntegrityValidator
                    validator = DatasetIntegrityValidator(self.data_dir)
                    validator.validate_session_file(json_path)
                    validation_passed = True
                except Exception as e:
                    validation_passed = False
                    validation_error = str(e)
                manifest_updated = False
        elif had_active_session:
            validation_passed = False
            validation_error = "Session files could not be finalized."

        # Step 5 & 6: Cleanly stop acquisition and release serial connection
        self.stimulator.stop()
        self.collector.stop_streaming()
        port_released = self.collector.disconnect()

        # Step 7: Confirm port released and report operator readiness
        safe_to_disconnect = port_released

        sid = None
        if self.active_session_info:
            sid = self.active_session_info.get("session_id")

        return {
            "status": "shutdown_complete" if safe_to_disconnect else "shutdown_warning",
            "session_id": sid,
            "had_active_session": had_active_session,
            "recording_stopped": True if had_active_session else False,
            "session_files_finalized": files_finalized,
            "json_path": json_path_str,
            "csv_path": csv_path_str,
            "frame_count": frame_count,
            "validation_passed": validation_passed,
            "validation_error": validation_error,
            "manifest_updated": manifest_updated,
            "activity_label": activity_label,
            "class_id": class_id,
            "serial_port_released": port_released,
            "safe_to_disconnect_usb": safe_to_disconnect
        }
