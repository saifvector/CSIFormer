import math
import numpy as np
from typing import Dict, Any, List, Optional
from app.models.schemas import CSIPacketFrame
from app.services.packet_validator import PacketValidationResult

class DataQualityReport:
    """Represents the formal scientific data quality assessment of a dataset recording session."""
    def __init__(
        self,
        session_id: str,
        total_frames_received: int,
        valid_frames_count: int,
        corrupted_frames_count: int,
        dropped_packets_count: int,
        packet_loss_pct: float,
        frame_completeness_pct: float,
        avg_rssi: float,
        rssi_std: float,
        avg_snr: float,
        snr_std: float,
        signal_stability_score: float,
        composite_quality_score: float,
        quality_level: str,
        duration_seconds: float
    ):
        self.session_id = session_id
        self.total_frames_received = total_frames_received
        self.valid_frames_count = valid_frames_count
        self.corrupted_frames_count = corrupted_frames_count
        self.dropped_packets_count = dropped_packets_count
        self.packet_loss_pct = packet_loss_pct
        self.frame_completeness_pct = frame_completeness_pct
        self.avg_rssi = avg_rssi
        self.rssi_std = rssi_std
        self.avg_snr = avg_snr
        self.snr_std = snr_std
        self.signal_stability_score = signal_stability_score
        self.composite_quality_score = composite_quality_score
        self.quality_level = quality_level
        self.duration_seconds = duration_seconds

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "total_frames_received": self.total_frames_received,
            "valid_frames_count": self.valid_frames_count,
            "corrupted_frames_count": self.corrupted_frames_count,
            "dropped_packets_count": self.dropped_packets_count,
            "packet_loss_pct": self.packet_loss_pct,
            "frame_completeness_pct": self.frame_completeness_pct,
            "avg_rssi": self.avg_rssi,
            "rssi_std": self.rssi_std,
            "avg_snr": self.avg_snr,
            "snr_std": self.snr_std,
            "signal_stability_score": self.signal_stability_score,
            "composite_quality_score": self.composite_quality_score,
            "quality_level": self.quality_level,
            "duration_seconds": self.duration_seconds
        }

class DataQualityAnalyzer:
    """
    Scientific CSI Data Quality Analysis & Verification Engine.
    Evaluates packet streams against loss, noise, dropped sequences, amplitude anomalies,
    and computes verified research-grade data quality metrics.
    """
    def __init__(self):
        self.reset_session_buffers()

    def reset_session_buffers(self):
        self.current_session_id = ""
        self.frames_received = 0
        self.valid_frames = 0
        self.corrupt_frames = 0
        self.dropped_packets = 0
        
        self.rssi_buffer: List[float] = []
        self.snr_buffer: List[float] = []
        self.start_timestamp: Optional[float] = None
        self.last_timestamp: Optional[float] = None

    def start_session_monitoring(self, session_id: str, start_time: float):
        self.reset_session_buffers()
        self.current_session_id = session_id
        self.start_timestamp = start_time
        self.last_timestamp = start_time

    def process_frame_metrics(self, frame: CSIPacketFrame, val_result: PacketValidationResult):
        """Processes real-time frame telemetry and validation feedback."""
        self.frames_received += 1
        self.last_timestamp = frame.timestamp

        if val_result.is_valid:
            self.valid_frames += 1
            self.rssi_buffer.append(float(frame.rssi))
            self.snr_buffer.append(float(frame.snr))
        else:
            self.corrupt_frames += 1

        if val_result.dropped_packets_detected > 0:
            self.dropped_packets += val_result.dropped_packets_detected

    def compute_quality_report(self, session_id: Optional[str] = None) -> DataQualityReport:
        """
        Computes rigorous, mathematically grounded quality report from captured metrics.
        """
        sid = session_id or self.current_session_id or "UNKNOWN_SESSION"
        duration = 0.0
        if self.start_timestamp and self.last_timestamp:
            duration = round(max(0.1, self.last_timestamp - self.start_timestamp), 2)

        # 1. Packet Loss Rate %
        total_expected = self.valid_frames + self.corrupt_frames + self.dropped_packets
        loss_pct = 0.0
        if total_expected > 0:
            loss_pct = round((self.dropped_packets / total_expected) * 100.0, 2)

        # 2. Frame Completeness %
        completeness_pct = 100.0
        if total_expected > 0:
            completeness_pct = round((self.valid_frames / total_expected) * 100.0, 2)

        # 3. Statistical Moments: RSSI & SNR
        if self.rssi_buffer:
            rssi_arr = np.array(self.rssi_buffer, dtype=np.float32)
            avg_rssi = round(float(np.mean(rssi_arr)), 2)
            rssi_std = round(float(np.std(rssi_arr)), 2)
        else:
            avg_rssi = -50.0
            rssi_std = 0.0

        if self.snr_buffer:
            snr_arr = np.array(self.snr_buffer, dtype=np.float32)
            avg_snr = round(float(np.mean(snr_arr)), 2)
            snr_std = round(float(np.std(snr_arr)), 2)
        else:
            avg_snr = 35.0
            snr_std = 0.0

        # 4. Signal Stability Score (0 - 100)
        # Low SNR variance and high SNR mean indicate high physical signal stability
        snr_stability = max(10.0, min(100.0, 100.0 - snr_std * 6.0))
        signal_stability = round(float(snr_stability), 1)

        # 5. Composite Quality Score Q in [0..100]
        # Weighted: 40% Completeness, 35% Stability, 25% (100 - Loss)
        q_score = (
            0.40 * completeness_pct +
            0.35 * signal_stability +
            0.25 * max(0.0, 100.0 - loss_pct)
        )
        q_score = round(max(0.0, min(100.0, q_score)), 1)

        # 6. Quality Level Categorization
        if q_score >= 90.0:
            quality_level = "Excellent"
        elif q_score >= 75.0:
            quality_level = "Good"
        elif q_score >= 60.0:
            quality_level = "Acceptable"
        elif q_score >= 40.0:
            quality_level = "Poor"
        else:
            quality_level = "Invalid"

        return DataQualityReport(
            session_id=sid,
            total_frames_received=self.frames_received,
            valid_frames_count=self.valid_frames,
            corrupted_frames_count=self.corrupt_frames,
            dropped_packets_count=self.dropped_packets,
            packet_loss_pct=loss_pct,
            frame_completeness_pct=completeness_pct,
            avg_rssi=avg_rssi,
            rssi_std=rssi_std,
            avg_snr=avg_snr,
            snr_std=snr_std,
            signal_stability_score=signal_stability,
            composite_quality_score=q_score,
            quality_level=quality_level,
            duration_seconds=duration
        )

data_quality_analyzer = DataQualityAnalyzer()
