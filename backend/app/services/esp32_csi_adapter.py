"""
ESP32-S3 Transfer Learning Adapter for CSIFormer.

Provides cross-hardware subcarrier alignment, antenna stream reduction,
temporal resampling, and phase sanitization to map benchmark CSI datasets
(Intel 5300 / Widar 3.0 and Atheros / NTU-Fi HAR) directly to ESP32-S3
hardware representations.
"""

from typing import Dict, Any, Tuple, Optional
import numpy as np
from scipy import interpolate


class ESP32CSIAdapter:
    """
    Standardized adapter for mapping multi-platform CSI datasets
    to ESP32-S3 CSI format (56 subcarriers in HT20, 114 subcarriers in HT40).
    """

    # 802.11n subcarrier index definitions
    # Intel 5300 (30 subcarriers sampled per carrier frequency)
    INTEL5300_SUBCARRIERS = np.array([
        -28, -26, -24, -22, -20, -18, -16, -14, -12, -10, -8, -6, -4, -2, -1,
        1, 3, 5, 7, 9, 11, 13, 15, 17, 19, 21, 23, 25, 27, 28
    ])

    # ESP32-S3 HT20 (56 usable subcarriers: -28 to -1, 1 to 28)
    ESP32_HT20_SUBCARRIERS = np.concatenate([
        np.arange(-28, 0),
        np.arange(1, 29)
    ])

    # Atheros / ESP32-S3 HT40 (114 usable subcarriers)
    ATHEROS_HT40_SUBCARRIERS = np.concatenate([
        np.arange(-58, -1),
        np.arange(2, 59)
    ])

    def __init__(self, target_mode: str = "HT20", target_rate_hz: float = 30.0):
        """
        Initialize the adapter.
        :param target_mode: Target ESP32-S3 Wi-Fi channel mode ("HT20" -> 56 subcarriers, "HT40" -> 114 subcarriers).
        :param target_rate_hz: Target frame rate in Hz (default: 30 Hz for CSIFormer live engine).
        """
        self.target_mode = target_mode
        self.target_rate_hz = target_rate_hz
        self.target_subcarriers = 56 if target_mode == "HT20" else 114

    def intel5300_to_esp32(self, csi_amplitude: np.ndarray) -> np.ndarray:
        """
        Map Intel 5300 CSI amplitude (30 subcarriers) to ESP32-S3 (56 or 114 subcarriers)
        using cubic spline interpolation along the subcarrier axis.
        
        :param csi_amplitude: Input array with shape (..., 30, T) or (..., 30).
        :return: Transformed array with shape (..., target_subcarriers, T) or (..., target_subcarriers).
        """
        original_shape = csi_amplitude.shape
        # Identify the subcarrier dimension (size 30)
        subcarrier_axis = None
        for ax, dim in enumerate(original_shape):
            if dim == 30:
                subcarrier_axis = ax
                break

        if subcarrier_axis is None:
            raise ValueError(f"Input csi_amplitude does not have a dimension of size 30. Shape: {original_shape}")

        target_grid = self.ESP32_HT20_SUBCARRIERS if self.target_mode == "HT20" else np.linspace(-58, 58, 114)
        
        # Apply interpolation along the subcarrier axis
        interpolator = interpolate.interp1d(
            self.INTEL5300_SUBCARRIERS,
            csi_amplitude,
            axis=subcarrier_axis,
            kind="cubic",
            fill_value="extrapolate"
        )
        return interpolator(target_grid)

    def atheros_to_esp32(self, csi_amplitude: np.ndarray) -> np.ndarray:
        """
        Map Atheros CSI amplitude (114 subcarriers) to ESP32-S3 format:
        - For HT40 target: direct 114-subcarrier match.
        - For HT20 target: center-channel decimation to 56 subcarriers.
        
        :param csi_amplitude: Input array with shape (..., 114, T) or (..., 114).
        :return: Transformed array with shape (..., target_subcarriers, T).
        """
        original_shape = csi_amplitude.shape
        subcarrier_axis = None
        for ax, dim in enumerate(original_shape):
            if dim == 114:
                subcarrier_axis = ax
                break

        if subcarrier_axis is None:
            raise ValueError(f"Input csi_amplitude does not have a dimension of size 114. Shape: {original_shape}")

        if self.target_mode == "HT40":
            return csi_amplitude.copy()

        # Decimate / interpolate 114 subcarriers to 56 subcarriers for HT20 mode
        src_grid = np.linspace(-28, 28, 114)
        target_grid = self.ESP32_HT20_SUBCARRIERS
        interpolator = interpolate.interp1d(
            src_grid,
            csi_amplitude,
            axis=subcarrier_axis,
            kind="linear",
            fill_value="extrapolate"
        )
        return interpolator(target_grid)

    def normalize_antenna_stream(self, csi: np.ndarray, target_antennas: int = 1) -> np.ndarray:
        """
        Reduce multi-antenna CSI (e.g. 3 RX antennas from Intel 5300 or Atheros)
        to single-stream (1 antenna) or dual-antenna representation matching ESP32-S3.
        
        :param csi: Input array with antenna dimension (e.g., shape (3, subcarriers, T)).
        :param target_antennas: Desired number of antennas (default 1).
        :return: Normalized array (e.g., shape (1, subcarriers, T) or averaged).
        """
        if csi.shape[0] == target_antennas:
            return csi.copy()
        elif csi.shape[0] > target_antennas:
            # Average across the excess antenna dimension or select primary antenna
            if target_antennas == 1:
                return np.mean(csi, axis=0, keepdims=True)
            else:
                return csi[:target_antennas]
        else:
            # Tile antenna to match target
            repeat_factor = int(np.ceil(target_antennas / csi.shape[0]))
            return np.repeat(csi, repeat_factor, axis=0)[:target_antennas]

    def resample_temporal_rate(
        self,
        csi_sequence: np.ndarray,
        source_rate_hz: float,
        target_rate_hz: Optional[float] = None
    ) -> np.ndarray:
        """
        Resample temporal packets to target streaming frequency (e.g., 1000 Hz / 100 Hz -> 30 Hz).
        
        :param csi_sequence: Input array with time as the last dimension (shape: (..., T)).
        :param source_rate_hz: Source sampling frequency in Hz.
        :param target_rate_hz: Target sampling frequency in Hz (default: self.target_rate_hz).
        :return: Resampled array with shape (..., T_target).
        """
        target_rate = target_rate_hz or self.target_rate_hz
        if source_rate_hz == target_rate:
            return csi_sequence.copy()

        num_samples = csi_sequence.shape[-1]
        duration_sec = num_samples / source_rate_hz
        target_samples = max(1, int(np.round(duration_sec * target_rate)))

        t_src = np.linspace(0, duration_sec, num_samples)
        t_target = np.linspace(0, duration_sec, target_samples)

        interpolator = interpolate.interp1d(
            t_src,
            csi_sequence,
            axis=-1,
            kind="linear",
            fill_value="extrapolate"
        )
        return interpolator(t_target)

    def sanitize_phase(self, csi_phase: np.ndarray) -> np.ndarray:
        """
        Sanitize raw CSI phase by removing the linear phase ramp induced by
        sampling frequency offset (SFO) and packet timing offset (STO).
        
        :param csi_phase: Unwrapped phase array of shape (subcarriers, T).
        :return: Sanitized phase array of shape (subcarriers, T).
        """
        subcarriers = csi_phase.shape[0]
        idx = np.arange(subcarriers)
        # Linear regression per timestamp to remove slope and DC offset
        idx_centered = idx - np.mean(idx)
        denom = np.sum(idx_centered ** 2)

        if denom == 0:
            return csi_phase

        slopes = np.sum(csi_phase * idx_centered[:, None], axis=0) / denom
        offsets = np.mean(csi_phase, axis=0)

        linear_fit = offsets[None, :] + slopes[None, :] * idx_centered[:, None]
        return csi_phase - linear_fit

    def adapt_sample(
        self,
        csi_matrix: np.ndarray,
        source_type: str,
        source_rate_hz: float = 1000.0,
        target_antennas: int = 1
    ) -> Dict[str, Any]:
        """
        End-to-end transformation of a CSI sample to ESP32-S3 format.
        
        :param csi_matrix: Raw amplitude or complex CSI matrix.
        :param source_type: "intel5300" or "atheros".
        :param source_rate_hz: Source packet rate.
        :param target_antennas: Target antenna count.
        :return: Dict containing adapted matrix, metadata, and shape specs.
        """
        data = csi_matrix.copy()

        # Step 1: Subcarrier alignment
        if source_type.lower() in ("intel5300", "widar", "widar3"):
            data = self.intel5300_to_esp32(data)
        elif source_type.lower() in ("atheros", "ntufi", "ntu_fi"):
            data = self.atheros_to_esp32(data)
        else:
            raise ValueError(f"Unknown source_type: {source_type}")

        # Step 2: Antenna stream reduction
        if len(data.shape) == 3 and data.shape[0] > target_antennas:
            data = self.normalize_antenna_stream(data, target_antennas=target_antennas)

        # Step 3: Temporal rate alignment
        if len(data.shape) >= 2:
            data = self.resample_temporal_rate(data, source_rate_hz=source_rate_hz)

        # Step 4: Min-Max and L2 standardization
        min_val = np.min(data)
        max_val = np.max(data)
        if max_val > min_val:
            normalized = (data - min_val) / (max_val - min_val)
        else:
            normalized = data

        return {
            "adapted_csi": normalized,
            "target_mode": self.target_mode,
            "subcarriers": self.target_subcarriers,
            "sampling_rate_hz": self.target_rate_hz,
            "shape": normalized.shape
        }
