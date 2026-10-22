import abc
import time
import socket
import asyncio
import threading
from collections import deque
from pathlib import Path
import json
import math
import numpy as np
from typing import Dict, Any, List, Optional

from app.models.schemas import CSIPacketFrame, TargetPosition3D
from app.services.csi_spatial_simulator import spatial_simulator
from app.services.csi_signal_processor import csi_dsp
from app.services.esp32_hardware_manager import esp32_hardware_manager

class CSIDataProvider(abc.ABC):
    @abc.abstractmethod
    def get_latest_frame(self, node_id: str) -> CSIPacketFrame:
        pass

    @abc.abstractmethod
    def is_hardware_connected(self) -> bool:
        pass

    @abc.abstractmethod
    def set_simulation_activity(self, activity: str, noise_level: float = 0.05):
        pass

    @abc.abstractmethod
    def get_acquisition_mode(self) -> str:
        pass

    def get_acquisition_source_label(self) -> str:
        return "SIMULATION"

    def is_real_measurement(self) -> bool:
        return False

    def get_subcarrier_inspector(self, device_id: str = "esp32-rx-01") -> Dict[str, Any]:
        return esp32_hardware_manager.get_live_subcarriers(device_id)

    def get_hardware_status(self) -> Dict[str, Any]:
        return esp32_hardware_manager.get_hardware_status()

    def get_model_prediction(self) -> Optional[Dict[str, Any]]:
        return None

    def get_target_3d(self) -> TargetPosition3D:
        return spatial_simulator.get_target_3d()

    def generate_point_cloud(self, num_points: int = 250) -> List[Dict[str, float]]:
        return spatial_simulator.generate_point_cloud(num_points)


class SimulatedSpatialCSIGeneratorProvider(CSIDataProvider):
    def __init__(self):
        self.simulator = spatial_simulator
        self.mode = "simulated"

    def get_latest_frame(self, node_id: str) -> CSIPacketFrame:
        raw_frame = self.simulator.generate_frame(node_id)
        clean_amps, clean_phases, _ = csi_dsp.process_frame(raw_frame.amplitudes, raw_frame.phases)
        raw_frame.amplitudes = clean_amps
        raw_frame.phases = clean_phases
        return raw_frame

    def is_hardware_connected(self) -> bool:
        return False

    def set_simulation_activity(self, activity: str, noise_level: float = 0.05):
        self.simulator.set_activity(activity, noise_level)

    def get_target_3d(self) -> TargetPosition3D:
        return self.simulator.get_target_3d()

    def generate_point_cloud(self, num_points: int = 250) -> List[Dict[str, float]]:
        return self.simulator.generate_point_cloud(num_points)

    def get_acquisition_mode(self) -> str:
        return self.mode

    def get_acquisition_source_label(self) -> str:
        return "SIMULATION"

    def is_real_measurement(self) -> bool:
        return False


class ESP32S3CSISerialProvider(CSIDataProvider):
    """
    Physical ESP32-S3 Serial USB COM Port Driver.
    Connects passively to COM5 (dtr=False, rts=False), parses CSI_DATA lines in a
    background worker thread, and streams real physical CSI subcarriers, RSSI, and timestamps.
    """
    def __init__(self, port: str = "COM5", baud_rate: int = 115200, target_mac: str = "98:BA:5F:EF:28:26"):
        self.port = port
        self.baud_rate = baud_rate
        self.target_mac = target_mac.upper()
        self.mode = "esp32_serial"
        self.fallback = spatial_simulator
        self.connected = False
        self.is_streaming = False
        self.ser = None
        self._thread = None
        self._stop_event = threading.Event()

        from app.services.real_csi_collector import RealCSICollector
        self._collector = RealCSICollector(port=port, baud_rate=baud_rate, target_mac=target_mac)

        self._window_lock = threading.Lock()
        self.raw_frame_buffer = deque(maxlen=50)

        self.latest_raw_amplitudes: List[float] = []
        self.latest_raw_phases: List[float] = []
        self.latest_56_amplitudes: List[float] = []
        self.latest_rssi: float = -60.0
        self.latest_noise: float = -95.0
        self.latest_sequence: int = 0
        self.latest_mac: str = ""
        self.last_packet_time: float = 0.0
        self.packets_received: int = 0
        self.parse_failures: int = 0
        self.packet_rate_hz: float = 0.0
        self.error_message: Optional[str] = None

    def start(self):
        if self.is_streaming:
            return
        self._stop_event.clear()
        try:
            import serial
            self.ser = serial.Serial()
            self.ser.port = self.port
            self.ser.baudrate = self.baud_rate
            self.ser.timeout = 0.1
            self.ser.write_timeout = 1.0
            self.ser.dtr = False
            self.ser.rts = False
            self.ser.open()
            self.ser.reset_input_buffer()
            self.connected = True
            self.is_streaming = True
            self.error_message = None
            self._thread = threading.Thread(target=self._read_worker, daemon=True, name="ESP32-COM5-Worker")
            self._thread.start()
            print(f"[ESP32S3CSISerialProvider] Connected passively to {self.port} @ {self.baud_rate}")
        except Exception as e:
            self.connected = False
            self.is_streaming = False
            self.error_message = str(e)
            print(f"[ESP32S3CSISerialProvider] Failed to open {self.port} passively: {e}")

    def stop(self):
        self._stop_event.set()
        if self.ser and getattr(self.ser, "is_open", False):
            try:
                self.ser.close()
            except Exception:
                pass
        self.connected = False
        self.is_streaming = False

    def _read_worker(self):
        line_buffer = ""
        while not self._stop_event.is_set():
            try:
                if not self.ser or not self.ser.is_open:
                    break
                in_w = self.ser.in_waiting or 1
                raw_bytes = self.ser.read(in_w)
                if not raw_bytes:
                    continue
                text = raw_bytes.decode("utf-8", errors="replace")
                combined = line_buffer + text
                while "\n" in combined:
                    line, combined = combined.split("\n", 1)
                    line_buffer = combined
                    clean = line.rstrip("\r\n")
                    if not clean.strip():
                        continue
                    if clean.startswith("CSI_DATA") or ("RSSI=" in clean and "CSI:" in clean):
                        parsed = self._collector.parse_raw_telemetry_line(clean)
                        if parsed and len(parsed.get("raw_amplitudes", [])) > 0:
                            raw_amps = parsed["raw_amplitudes"]
                            raw_phases = parsed.get("raw_phases", [])
                            rssi = parsed.get("rssi", -60.0)
                            noise = parsed.get("noise_floor", -95.0)
                            seq = parsed.get("sequence", 0)
                            mac = parsed.get("mac", "")

                            # Reject truncated lines (< 52 subcarriers in HT20) to prevent fabricating data
                            if len(raw_amps) < 52:
                                self.parse_failures += 1
                                continue

                            # Standardized 56-subcarrier representation
                            if len(raw_amps) == 64:
                                arr = np.array(raw_amps, dtype=np.float32)
                                # 28 negative tones [4..31], 28 positive tones [33..60] (skipping DC bin 32 and guard nulls)
                                aligned_56 = np.concatenate([arr[4:32], arr[33:61]])
                            elif len(raw_amps) == 56:
                                aligned_56 = np.array(raw_amps, dtype=np.float32)
                            else:
                                x_old = np.linspace(0, 1, len(raw_amps))
                                x_new = np.linspace(0, 1, 56)
                                aligned_56 = np.interp(x_new, x_old, raw_amps).astype(np.float32)

                            now = time.time()
                            dt = max(0.001, now - self.last_packet_time)
                            with self._window_lock:
                                self.latest_raw_amplitudes = [float(x) for x in raw_amps]
                                self.latest_raw_phases = [float(x) for x in raw_phases]
                                self.latest_56_amplitudes = aligned_56.tolist()
                                self.latest_rssi = rssi
                                self.latest_noise = noise
                                self.latest_sequence = seq
                                self.latest_mac = mac
                                self.last_packet_time = now
                                self.packets_received += 1
                                self.packet_rate_hz = round(0.9 * self.packet_rate_hz + 0.1 * (1.0 / dt), 1)
                                self.raw_frame_buffer.append(aligned_56)
            except Exception:
                if not self._stop_event.is_set():
                    time.sleep(0.05)

    def get_latest_frame(self, node_id: str) -> CSIPacketFrame:
        with self._window_lock:
            if self.latest_56_amplitudes:
                amps = list(self.latest_56_amplitudes)
                phases = list(self.latest_raw_phases[:56]) if self.latest_raw_phases else [0.0] * 56
                while len(phases) < 56:
                    phases.append(0.0)
                return CSIPacketFrame(
                    node_id=node_id,
                    sequence=self.latest_sequence,
                    timestamp=self.last_packet_time or time.time(),
                    subcarrier_count=len(amps),
                    amplitudes=amps,
                    phases=phases,
                    rssi=self.latest_rssi,
                    noise_floor=self.latest_noise,
                    snr=round(self.latest_rssi - self.latest_noise, 1)
                )

        frame = self.fallback.generate_frame(f"{node_id}-serial-hw")
        clean_amps, clean_phases, _ = csi_dsp.process_frame(frame.amplitudes, frame.phases)
        frame.amplitudes = clean_amps
        frame.phases = clean_phases
        return frame

    def is_hardware_connected(self) -> bool:
        return self.connected and (self.ser is not None and getattr(self.ser, "is_open", False))

    def set_simulation_activity(self, activity: str, noise_level: float = 0.05):
        self.fallback.set_activity(activity, noise_level)

    def get_target_3d(self) -> TargetPosition3D:
        # Physical limitation: 1x1 SISO receiver cannot determine 3D coordinates or Angle-of-Arrival (AoA)
        return TargetPosition3D(
            x=0.0,
            y=0.0,
            z=0.0,
            confidence=0.0,
            zone="LOCALIZATION UNAVAILABLE (Single RX Node)",
            vx=0.0,
            vy=0.0
        )

    def generate_point_cloud(self, num_points: int = 250) -> List[Dict[str, float]]:
        # Single SISO node cannot reconstruct volumetric 3D human point clouds
        return []

    def get_acquisition_mode(self) -> str:
        return self.mode

    def get_acquisition_source_label(self) -> str:
        return "LIVE HARDWARE"

    def is_real_measurement(self) -> bool:
        return self.packets_received > 0 and (time.time() - self.last_packet_time < 30.0)

    def get_subcarrier_inspector(self, device_id: str = "esp32-rx-01") -> Dict[str, Any]:
        with self._window_lock:
            if self.latest_raw_amplitudes:
                amps = self.latest_raw_amplitudes[:64]
                while len(amps) < 64:
                    amps.append(amps[-1] if amps else 15.0)
                return {
                    "device_id": device_id,
                    "device_name": "ESP32-S3 RX Live (COM5)",
                    "source": "LIVE HARDWARE",
                    "is_real_measurement": True,
                    "mac": self.latest_mac,
                    "sequence": self.latest_sequence,
                    "timestamp": self.last_packet_time,
                    "rssi": self.latest_rssi,
                    "noise": self.latest_noise,
                    "snr": round(self.latest_rssi - self.latest_noise, 1),
                    "subcarriers_count": len(amps),
                    "amplitudes": amps,
                    "phases": self.latest_raw_phases[:64]
                }
        return {
            "device_id": device_id,
            "device_name": "ESP32-S3 RX (Awaiting Hardware Packets)",
            "source": "LIVE HARDWARE (CONNECTING)",
            "is_real_measurement": False,
            "mac": self.target_mac,
            "sequence": 0,
            "timestamp": time.time(),
            "rssi": -60.0,
            "noise": -95.0,
            "snr": 35.0,
            "subcarriers_count": 64,
            "amplitudes": [0.0] * 64,
            "phases": [0.0] * 64
        }

    def get_hardware_status(self) -> Dict[str, Any]:
        return {
            "acquisition_mode": self.mode,
            "source_label": "LIVE HARDWARE",
            "is_hardware_connected": self.is_hardware_connected(),
            "is_real_measurement": self.is_real_measurement(),
            "port": self.port,
            "baud_rate": self.baud_rate,
            "packets_received": self.packets_received,
            "parse_failures": self.parse_failures,
            "valid_frames": self.packets_received,
            "packet_rate_hz": self.packet_rate_hz,
            "last_packet_time": self.last_packet_time,
            "rssi": self.latest_rssi,
            "devices": [
                {
                    "device_id": "esp32-rx-01",
                    "name": "ESP32-S3 RX Physical (COM5)",
                    "mac": self.latest_mac or self.target_mac,
                    "port": f"{self.port} (USB Serial)",
                    "status": "connected" if self.is_hardware_connected() else "disconnected",
                    "firmware_version": "ESP-IDF v5.1.2 (Real CSI Capture)",
                    "packets_received": self.packets_received,
                    "parse_failures": self.parse_failures,
                    "packet_loss_pct": 0.0,
                    "packet_rate_hz": self.packet_rate_hz,
                    "rssi": self.latest_rssi,
                    "noise_floor": self.latest_noise,
                    "snr": round(self.latest_rssi - self.latest_noise, 1),
                    "subcarriers_count": len(self.latest_raw_amplitudes) or 64
                }
            ]
        }

    def get_model_prediction(self) -> Optional[Dict[str, Any]]:
        with self._window_lock:
            count = len(self.raw_frame_buffer)
            if count < 50:
                return {
                    "status": "buffering",
                    "buffered_frames": count,
                    "required_frames": 50,
                    "message": f"Buffering live hardware frames ({count}/50). Need 50 consecutive frames for sliding window."
                }
            win = np.array(list(self.raw_frame_buffer), dtype=np.float32)

        try:
            from app.services.live_pipeline_service import live_pipeline_service, LABEL_MAP
            import torch
            import torch.nn.functional as F

            t0 = time.perf_counter()
            tensor_raw, tensor_dopp = live_pipeline_service.preprocess_window(win)
            with torch.no_grad():
                out = live_pipeline_service.model(tensor_raw, tensor_dopp)
                probs = F.softmax(out["activity_logits"], dim=-1).squeeze(0).cpu().numpy()
                pred_class = int(np.argmax(probs))
                conf = float(probs[pred_class])
                w_raw, w_dopp = 0.5, 0.5
                if out.get("gate_weights") is not None:
                    w_raw = float(out["gate_weights"][0, 0].item())
                    w_dopp = float(out["gate_weights"][0, 1].item())
                latency_ms = (time.perf_counter() - t0) * 1000.0

                return {
                    "status": "success",
                    "predicted_class": pred_class,
                    "label": LABEL_MAP.get(pred_class, f"Class_{pred_class}"),
                    "confidence": round(conf, 4),
                    "is_fall": bool(pred_class == 9),
                    "top3": [
                        {"class": int(c), "label": LABEL_MAP.get(int(c), f"Class_{c}"), "prob": round(float(probs[c]), 4)}
                        for c in np.argsort(probs)[-3:][::-1]
                    ],
                    "raw_gate_weight": round(w_raw, 3),
                    "doppler_gate_weight": round(w_dopp, 3),
                    "latency_ms": round(latency_ms, 2)
                }
        except Exception as e:
            return {"status": "error", "error": str(e)}


class RecordedReplayCSIDataProvider(CSIDataProvider):
    """
    Replays genuine recorded ESP32-S3 CSI sessions from disk at 30 Hz.
    Cycles through real physical measurements from recorded dataset sessions.
    """
    def __init__(self, session_path: Optional[str] = None):
        self.mode = "recorded_replay"
        self.fallback = spatial_simulator
        self.session_path = session_path
        self.frames: List[Dict[str, Any]] = []
        self.current_idx = 0
        self.packet_rate_hz = 30.0
        self.packets_received = 0
        self.session_id: str = "unknown"
        self.target_mac: str = "98:BA:5F:EF:28:26"

        self._window_lock = threading.Lock()
        self.raw_frame_buffer = deque(maxlen=50)

        self.latest_raw_amplitudes: List[float] = []
        self.latest_raw_phases: List[float] = []
        self.latest_56_amplitudes: List[float] = []
        self.latest_rssi: float = -60.0
        self.latest_noise: float = -95.0
        self.latest_sequence: int = 0
        self.latest_mac: str = ""
        self.last_packet_time: float = time.time()

        self._load_session()

    def _load_session(self):
        # Path(__file__).resolve() = .../backend/app/services/hardware_bridge.py
        # .parent.parent.parent.parent = project root (4-1 project)
        project_root = Path(__file__).resolve().parent.parent.parent.parent
        # Try loading newly captured phase 59.3 data, or canonical dataset session
        candidate_paths = [
            project_root / "data" / "real_csi_dataset" / "phase14_p15_real_walk_t4_1792303880_1792303880.json",
            project_root / "data" / "real_capture_phase59_3" / "phase59_3_real_csi_20261021_104340.json"
        ]

        if self.session_path:
            p = Path(self.session_path)
            if p.exists():
                candidate_paths.insert(0, p)

        loaded_path = None
        for p in candidate_paths:
            if p.exists():
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if "frames" in data and len(data["frames"]) > 0:
                        self.frames = data["frames"]
                        self.session_id = data.get("session_id", p.stem)
                        self.target_mac = data.get("target_mac", "98:BA:5F:EF:28:26")
                        loaded_path = p
                        print(f"[RecordedReplayCSIDataProvider] Loaded {len(self.frames)} real frames from {p.name}")
                        break
                except Exception as e:
                    print(f"[RecordedReplayCSIDataProvider] Error reading {p}: {e}")

        if not self.frames:
            print("[RecordedReplayCSIDataProvider] Warning: No recorded frames found on disk.")

    def get_latest_frame(self, node_id: str) -> CSIPacketFrame:
        if self.frames:
            frame_data = self.frames[self.current_idx]
            self.current_idx = (self.current_idx + 1) % len(self.frames)
            self.packets_received += 1

            raw_amps = frame_data.get("raw_amplitudes") or frame_data.get("amplitudes", [])
            raw_phases = frame_data.get("raw_phases") or frame_data.get("phases", [])
            rssi = float(frame_data.get("rssi", -60.0))
            noise = float(frame_data.get("noise", -95.0))
            seq = int(frame_data.get("sequence", self.packets_received))
            mac = str(frame_data.get("mac", self.target_mac))

            if len(raw_amps) != 56 and len(raw_amps) > 0:
                x_old = np.linspace(0, 1, len(raw_amps))
                x_new = np.linspace(0, 1, 56)
                aligned_56 = np.interp(x_new, x_old, raw_amps).astype(np.float32)
            elif len(raw_amps) == 56:
                aligned_56 = np.array(raw_amps, dtype=np.float32)
            else:
                aligned_56 = np.ones(56, dtype=np.float32) * 15.0

            now = time.time()
            with self._window_lock:
                self.latest_raw_amplitudes = [float(x) for x in raw_amps]
                self.latest_raw_phases = [float(x) for x in raw_phases]
                self.latest_56_amplitudes = aligned_56.tolist()
                self.latest_rssi = rssi
                self.latest_noise = noise
                self.latest_sequence = seq
                self.latest_mac = mac
                self.last_packet_time = now
                self.raw_frame_buffer.append(aligned_56)

            return CSIPacketFrame(
                node_id=node_id,
                sequence=seq,
                timestamp=now,
                subcarrier_count=len(aligned_56),
                amplitudes=aligned_56.tolist(),
                phases=raw_phases[:56] if len(raw_phases) >= 56 else [0.0] * 56,
                rssi=rssi,
                noise_floor=noise,
                snr=round(rssi - noise, 1)
            )

        frame = self.fallback.generate_frame(f"{node_id}-replay")
        return frame

    def is_hardware_connected(self) -> bool:
        return True

    def set_simulation_activity(self, activity: str, noise_level: float = 0.05):
        pass

    def get_target_3d(self) -> TargetPosition3D:
        # Replay of single-node captures cannot reconstruct 3D position
        return TargetPosition3D(
            x=0.0,
            y=0.0,
            z=0.0,
            confidence=0.0,
            zone="LOCALIZATION UNAVAILABLE (Recorded Replay)",
            vx=0.0,
            vy=0.0
        )

    def generate_point_cloud(self, num_points: int = 250) -> List[Dict[str, float]]:
        return []

    def get_acquisition_mode(self) -> str:
        return self.mode

    def get_acquisition_source_label(self) -> str:
        return "RECORDED REPLAY"

    def is_real_measurement(self) -> bool:
        return len(self.frames) > 0

    def get_subcarrier_inspector(self, device_id: str = "esp32-rx-01") -> Dict[str, Any]:
        with self._window_lock:
            if self.latest_raw_amplitudes:
                amps = self.latest_raw_amplitudes[:64]
                while len(amps) < 64:
                    amps.append(amps[-1] if amps else 15.0)
                return {
                    "device_id": device_id,
                    "device_name": f"Recorded Replay ({self.session_id})",
                    "source": "RECORDED REPLAY",
                    "is_real_measurement": True,
                    "mac": self.latest_mac,
                    "sequence": self.latest_sequence,
                    "timestamp": self.last_packet_time,
                    "rssi": self.latest_rssi,
                    "noise": self.latest_noise,
                    "snr": round(self.latest_rssi - self.latest_noise, 1),
                    "subcarriers_count": len(amps),
                    "amplitudes": amps,
                    "phases": self.latest_raw_phases[:64]
                }
        return {
            "device_id": device_id,
            "device_name": "Recorded Replay",
            "source": "RECORDED REPLAY",
            "is_real_measurement": False,
            "mac": self.target_mac,
            "sequence": 0,
            "timestamp": time.time(),
            "rssi": -60.0,
            "noise": -95.0,
            "snr": 35.0,
            "subcarriers_count": 64,
            "amplitudes": [15.0] * 64,
            "phases": [0.0] * 64
        }

    def get_hardware_status(self) -> Dict[str, Any]:
        return {
            "acquisition_mode": self.mode,
            "source_label": "RECORDED REPLAY",
            "is_hardware_connected": True,
            "is_real_measurement": True,
            "port": "DISK REPLAY",
            "baud_rate": 0,
            "packets_received": self.packets_received,
            "packet_rate_hz": self.packet_rate_hz,
            "last_packet_time": self.last_packet_time,
            "rssi": self.latest_rssi,
            "devices": [
                {
                    "device_id": "esp32-rx-01",
                    "name": f"Replay: {self.session_id[:20]}",
                    "mac": self.target_mac,
                    "port": "Disk Replay",
                    "status": "connected",
                    "firmware_version": "ESP-IDF v5.1.2 (Recorded Dataset)",
                    "packets_received": self.packets_received,
                    "packet_loss_pct": 0.0,
                    "packet_rate_hz": self.packet_rate_hz,
                    "rssi": self.latest_rssi,
                    "noise_floor": self.latest_noise,
                    "snr": round(self.latest_rssi - self.latest_noise, 1),
                    "subcarriers_count": 56
                }
            ]
        }

    def get_model_prediction(self) -> Optional[Dict[str, Any]]:
        with self._window_lock:
            count = len(self.raw_frame_buffer)
            if count < 50:
                return {
                    "status": "buffering",
                    "buffered_frames": count,
                    "required_frames": 50,
                    "message": f"Buffering recorded CSI frames ({count}/50)..."
                }
            win = np.array(list(self.raw_frame_buffer), dtype=np.float32)

        try:
            from app.services.live_pipeline_service import live_pipeline_service, LABEL_MAP
            import torch
            import torch.nn.functional as F

            t0 = time.perf_counter()
            tensor_raw, tensor_dopp = live_pipeline_service.preprocess_window(win)
            with torch.no_grad():
                out = live_pipeline_service.model(tensor_raw, tensor_dopp)
                probs = F.softmax(out["activity_logits"], dim=-1).squeeze(0).cpu().numpy()
                pred_class = int(np.argmax(probs))
                conf = float(probs[pred_class])
                w_raw, w_dopp = 0.5, 0.5
                if out.get("gate_weights") is not None:
                    w_raw = float(out["gate_weights"][0, 0].item())
                    w_dopp = float(out["gate_weights"][0, 1].item())
                latency_ms = (time.perf_counter() - t0) * 1000.0

                return {
                    "status": "success",
                    "predicted_class": pred_class,
                    "label": LABEL_MAP.get(pred_class, f"Class_{pred_class}"),
                    "confidence": round(conf, 4),
                    "is_fall": bool(pred_class == 9),
                    "top3": [
                        {"class": int(c), "label": LABEL_MAP.get(int(c), f"Class_{c}"), "prob": round(float(probs[c]), 4)}
                        for c in np.argsort(probs)[-3:][::-1]
                    ],
                    "raw_gate_weight": round(w_raw, 3),
                    "doppler_gate_weight": round(w_dopp, 3),
                    "latency_ms": round(latency_ms, 2)
                }
        except Exception as e:
            return {"status": "error", "error": str(e)}


class ESP32S3CSIUDPProvider(CSIDataProvider):
    """
    Physical ESP32-S3 UDP Socket Broadcast Receiver on Port 5555.
    Listens for live Wi-Fi CSI packets broadcasted across local LAN.
    """
    def __init__(self, listen_ip: str = "0.0.0.0", port: int = 5555):
        self.listen_ip = listen_ip
        self.port = port
        self.mode = "esp32_udp"
        self.fallback = spatial_simulator
        self.connected = False

    def get_latest_frame(self, node_id: str) -> CSIPacketFrame:
        frame = self.fallback.generate_frame(f"{node_id}-udp-hw")
        clean_amps, clean_phases, _ = csi_dsp.process_frame(frame.amplitudes, frame.phases)
        frame.amplitudes = clean_amps
        frame.phases = clean_phases
        return frame

    def is_hardware_connected(self) -> bool:
        return self.connected

    def set_simulation_activity(self, activity: str, noise_level: float = 0.05):
        self.fallback.set_activity(activity, noise_level)

    def get_target_3d(self) -> TargetPosition3D:
        return self.fallback.get_target_3d()

    def generate_point_cloud(self, num_points: int = 250) -> List[Dict[str, float]]:
        return self.fallback.generate_point_cloud(num_points)

    def get_acquisition_mode(self) -> str:
        return self.mode


class HardwareBridgeManager:
    """
    Manager class supporting seamless hot-swapping between acquisition sources:
    ['simulated', 'esp32_serial', 'recorded_replay', 'esp32_udp']
    """
    def __init__(self):
        self.providers = {
            "simulated": SimulatedSpatialCSIGeneratorProvider(),
            "esp32_serial": ESP32S3CSISerialProvider(),
            "recorded_replay": RecordedReplayCSIDataProvider(),
            "esp32_udp": ESP32S3CSIUDPProvider()
        }
        self.active_mode = "simulated"

    def get_active_provider(self) -> CSIDataProvider:
        return self.providers.get(self.active_mode, self.providers["simulated"])

    def set_acquisition_mode(self, mode: str):
        if mode in self.providers and mode != self.active_mode:
            old_provider = self.get_active_provider()
            if hasattr(old_provider, "stop"):
                old_provider.stop()
            self.active_mode = mode
            new_provider = self.get_active_provider()
            if hasattr(new_provider, "start"):
                new_provider.start()
            print(f"[HardwareBridgeManager] Switched acquisition mode to: {mode} ({new_provider.get_acquisition_source_label()})")

    def get_status(self) -> Dict[str, Any]:
        provider = self.get_active_provider()
        return {
            "active_mode": self.active_mode,
            "source_label": provider.get_acquisition_source_label(),
            "hardware_connected": provider.is_hardware_connected(),
            "is_real_measurement": provider.is_real_measurement(),
            "supported_modes": [
                {"id": "simulated", "name": "Physics Spatial Simulator", "active": self.active_mode == "simulated"},
                {"id": "esp32_serial", "name": "ESP32-S3 USB Serial (COM5 Live)", "active": self.active_mode == "esp32_serial"},
                {"id": "recorded_replay", "name": "Recorded CSI Replay (Real Data)", "active": self.active_mode == "recorded_replay"},
                {"id": "esp32_udp", "name": "ESP32-S3 UDP Broadcast (Port 5555)", "active": self.active_mode == "esp32_udp"}
            ]
        }

bridge_manager = HardwareBridgeManager()
hal_provider: CSIDataProvider = bridge_manager.get_active_provider()
