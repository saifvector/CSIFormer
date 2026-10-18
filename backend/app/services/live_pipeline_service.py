"""
Live Pipeline Service for CSIFormer Phase 14.

Coordinates:
RealCSICollector (Serial COM / Wi-Fi) -> PhysicsCSIPreprocessor -> CSIDualBranchFusionNet.
Exposes status, control (start/stop), and live prediction endpoints.
"""

import time
import threading
from pathlib import Path
from typing import Dict, Any, List, Optional
import numpy as np
import torch
import torch.nn.functional as F

from app.models.csiformer_dual_branch import CSIDualBranchFusionNet
from app.services.physics_csi_preprocessor import PhysicsCSIPreprocessor
from app.services.real_csi_collector import RealCSICollector


LABEL_MAP = {
    0: "Push&Pull (Widar)",
    1: "Sweep (Widar)",
    2: "Clap (Widar)",
    3: "Slide (Widar)",
    4: "Draw-O (Widar)",
    5: "Draw-Zigzag (Widar)",
    6: "Box (NTU-Fi)",
    7: "Circle (NTU-Fi)",
    8: "Clean (NTU-Fi)",
    9: "FALL DETECTION (NTU-Fi Life-Safety)",
    10: "Run (NTU-Fi)",
    11: "Walk (NTU-Fi)"
}


class LivePipelineService:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.collector: Optional[RealCSICollector] = None
        self.preprocessor = PhysicsCSIPreprocessor(
            carrier_freq=2.442e9,
            source_rate_hz=30.0,
            target_timesteps=50,
            target_channels=56,
            stft_window=32,
            stft_noverlap=24,
            stft_nfft=64
        )

        # Model initialization
        self.model: Optional[CSIDualBranchFusionNet] = None
        self._load_model()

        # Telemetry
        self.last_prediction: Optional[Dict[str, Any]] = None
        self.last_prediction_time: float = 0.0

    def _load_model(self):
        try:
            base_dir = Path(__file__).resolve().parent.parent.parent
            ckpt_path = base_dir.parent / "models" / "csiformer_phase13_best.pth"
            if not ckpt_path.exists():
                ckpt_path = base_dir / "models" / "csiformer_phase13_best.pth"
            if ckpt_path.exists():
                model = CSIDualBranchFusionNet(
                    num_subcarriers=56,
                    doppler_bins=56,
                    seq_len=50,
                    num_classes=12,
                    embed_dim=128,
                    nhead=8,
                    num_layers=3,
                    dim_feedforward=512,
                    dropout=0.1,
                    fusion_mode="gated"
                ).to(self.device)
                state = torch.load(ckpt_path, map_location=self.device, weights_only=True)
                model.load_state_dict(state)
                model.eval()
                self.model = model
            else:
                self.model = None
        except Exception as e:
            print(f"[LivePipelineService] Warning: Could not load model: {e}")
            self.model = None

    def start_collector(self, port: Optional[str] = None, baud_rate: int = 115200) -> Dict[str, Any]:
        if self.collector is not None and self.collector.is_streaming:
            return {
                "status": "already_running",
                "port": self.collector.port,
                "baud_rate": self.collector.baud_rate,
                "message": "Collector is already active."
            }

        self.collector = RealCSICollector(port=port, baud_rate=baud_rate)
        connected = self.collector.connect()
        if connected:
            self.collector.start_streaming()
            return {
                "status": "started",
                "port": self.collector.port,
                "baud_rate": self.collector.baud_rate,
                "message": f"Successfully connected and started stream on {self.collector.port}."
            }
        else:
            return {
                "status": "connection_failed",
                "port": port,
                "message": f"Could not connect to {port or 'auto-detected port'}. Ensure ESP32-S3 is connected."
            }

    def stop_collector(self) -> Dict[str, Any]:
        if self.collector is None or not self.collector.is_streaming:
            return {"status": "stopped", "message": "Collector is not running."}

        self.collector.stop_streaming()
        self.collector.disconnect()
        stats = self.collector.get_stats()
        return {
            "status": "stopped",
            "message": "Stream stopped and port closed.",
            "final_stats": stats
        }

    def get_status(self) -> Dict[str, Any]:
        if self.collector is None:
            return {
                "is_streaming": False,
                "is_connected": False,
                "port": None,
                "packets_received": 0,
                "packet_loss_pct": 0.0,
                "current_rate_hz": 0.0,
                "model_loaded": self.model is not None,
                "device": str(self.device)
            }
        stats = self.collector.get_stats()
        stats["model_loaded"] = self.model is not None
        stats["device"] = str(self.device)
        return stats

    def get_latest_window(self) -> Dict[str, Any]:
        if self.collector is None:
            return {"status": "no_collector", "window": None}

        raw_win, phase_win = self.collector.get_latest_window()
        if raw_win is None:
            return {"status": "buffering", "window": None, "buffered_frames": len(self.collector.raw_frame_buffer)}

        return {
            "status": "ready",
            "shape": list(raw_win.shape),
            "raw_amplitudes": raw_win.tolist(),
            "phases": phase_win.tolist() if phase_win is not None else None
        }

    def predict_latest_window(self) -> Dict[str, Any]:
        t0 = time.perf_counter()
        if self.model is None:
            return {"status": "error", "error": "Model checkpoint not loaded"}

        if self.collector is None:
            return {"status": "error", "error": "Collector not initialized"}

        raw_win, _ = self.collector.get_latest_window()
        if raw_win is None:
            return {
                "status": "buffering",
                "message": f"Collecting frames ({len(self.collector.raw_frame_buffer)}/50). Please wait."
            }

        # Validate
        if raw_win.shape != (50, 56) or not np.isfinite(raw_win).all():
            return {"status": "error", "error": f"Invalid window shape {raw_win.shape}"}

        # Normalize Raw Branch
        amp_mean = raw_win.mean(axis=0, keepdims=True)
        amp_std = raw_win.std(axis=0, keepdims=True) + 1e-6
        norm_raw = (raw_win - amp_mean) / amp_std
        tensor_raw = torch.tensor(norm_raw, dtype=torch.float32).unsqueeze(0).to(self.device)

        # Compute Doppler Branch
        doppler_mat = self.preprocessor.compute_doppler_spectrogram(raw_win)
        tensor_dopp = torch.tensor(doppler_mat, dtype=torch.float32).unsqueeze(0).to(self.device)

        with torch.no_grad():
            out = self.model(tensor_raw, tensor_dopp)
            probs = F.softmax(out["activity_logits"], dim=-1).squeeze(0).cpu().numpy()
            pred_class = int(np.argmax(probs))
            confidence = float(probs[pred_class])

            w_raw, w_dopp = 0.5, 0.5
            if out.get("fusion_weights") is not None:
                w_raw = float(out["fusion_weights"][0, 0].item())
                w_dopp = float(out["fusion_weights"][0, 1].item())

        total_ms = (time.perf_counter() - t0) * 1000.0

        res = {
            "status": "success",
            "predicted_class": pred_class,
            "label": LABEL_MAP.get(pred_class, f"Class_{pred_class}"),
            "confidence": round(confidence, 4),
            "is_fall": bool(pred_class == 9),
            "top3": [
                {"class": int(c), "label": LABEL_MAP.get(int(c), f"Class_{c}"), "prob": round(float(probs[c]), 4)}
                for c in np.argsort(probs)[-3:][::-1]
            ],
            "raw_gate_weight": round(w_raw, 3),
            "doppler_gate_weight": round(w_dopp, 3),
            "latency_ms": round(total_ms, 2)
        }
        self.last_prediction = res
        self.last_prediction_time = time.time()
        return res


live_pipeline_service = LivePipelineService()
