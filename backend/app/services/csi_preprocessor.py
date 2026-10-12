"""
CSI Preprocessing Engine for CSIFormer.

Provides production-grade signal processing for Wi-Fi Channel State Information (CSI):
- Amplitude & Phase Extraction
- Phase Unwrapping
- Phase Detrending (Linear Phase Ramp Removal)
- Zero-Phase Noise Filtering (Butterworth / Gaussian)
- Outlier Removal (Hampel Filter)
- Z-Score & Min-Max Normalization
- Temporal Resampling
- Window Segmentation
- Direct ESP32-S3 Subcarrier Grid Integration

Output Shape: [TimeSteps, Subcarriers] (e.g., [50, 56] for HT20 or [50, 114] for HT40).
"""

import math
from typing import Dict, Any, Optional, Tuple, Union
import numpy as np
import scipy.signal as signal
from scipy import interpolate
import torch

try:
    from app.services.esp32_csi_adapter import ESP32CSIAdapter
except ImportError:
    from esp32_csi_adapter import ESP32CSIAdapter


class CSIPreprocessor:
    """
    High-performance CSI preprocessing pipeline converting raw heterogeneous
    Wi-Fi CSI packets into standardized, sanitized, and normalized tensors for CSIFormer.
    """

    def __init__(
        self,
        target_mode: str = "HT20",
        target_timesteps: int = 50,
        filter_cutoff: float = 0.15,
        filter_order: int = 3,
        hampel_window: int = 7,
        hampel_n_sigmas: float = 3.0,
        normalize_method: str = "zscore"
    ):
        """
        Initialize the CSI Preprocessing Engine.

        :param target_mode: Target ESP32-S3 Wi-Fi channel ("HT20" -> 56 bins, "HT40" -> 114 bins).
        :param target_timesteps: Desired temporal sequence length (default: 50 packets).
        :param filter_cutoff: Normalized cutoff frequency for Butterworth low-pass filter (0 < Wn < 1).
        :param filter_order: Order of the Butterworth low-pass filter.
        :param hampel_window: Sliding window size for Hampel outlier detector.
        :param hampel_n_sigmas: Number of standard deviations for outlier thresholding.
        :param normalize_method: Normalization scheme ('zscore' or 'minmax').
        """
        self.target_mode = target_mode
        self.target_timesteps = target_timesteps
        self.target_subcarriers = 56 if target_mode.upper() == "HT20" else 114
        self.filter_cutoff = filter_cutoff
        self.filter_order = filter_order
        self.hampel_window = hampel_window
        self.hampel_n_sigmas = hampel_n_sigmas
        self.normalize_method = normalize_method

        # Initialize hardware adapter
        self.adapter = ESP32CSIAdapter(target_mode=target_mode, target_rate_hz=30.0)

        # Precompute Butterworth filter coefficients
        self.b_filter, self.a_filter = signal.butter(
            N=self.filter_order,
            Wn=self.filter_cutoff,
            btype="lowpass",
            analog=False
        )

    # --------------------------------------------------------------------------
    # 1. Amplitude & Phase Extraction
    # --------------------------------------------------------------------------
    @staticmethod
    def extract_amplitude(csi: np.ndarray) -> np.ndarray:
        """Extract magnitude / amplitude from complex CSI matrix."""
        if np.iscomplexobj(csi):
            return np.abs(csi).astype(np.float32)
        return np.asarray(csi, dtype=np.float32)

    @staticmethod
    def extract_phase(csi: np.ndarray) -> np.ndarray:
        """Extract raw phase angle from complex CSI matrix."""
        if np.iscomplexobj(csi):
            return np.angle(csi).astype(np.float32)
        return np.zeros_like(csi, dtype=np.float32)

    # --------------------------------------------------------------------------
    # 2. Phase Unwrapping & Linear Ramp Detrending
    # --------------------------------------------------------------------------
    @staticmethod
    def unwrap_phase(phase: np.ndarray, axis: int = -1) -> np.ndarray:
        """
        Unwrap phase across specified axis to eliminate 2*pi discontinuities.
        """
        return np.unwrap(phase, axis=axis).astype(np.float32)

    def detrend_phase(self, phase: np.ndarray) -> np.ndarray:
        """
        Remove linear phase slope caused by carrier frequency offset (CFO),
        sampling frequency offset (SFO), and packet detection delay (STO).
        
        Uses linear regression across the subcarrier dimension.
        :param phase: Phase array of shape (..., Subcarriers, TimeSteps) or (..., Subcarriers).
        """
        return self.adapter.sanitize_phase(phase)

    # --------------------------------------------------------------------------
    # 3. Noise Filtering (Zero-Phase Butterworth / Gaussian)
    # --------------------------------------------------------------------------
    def filter_noise(self, data: np.ndarray, axis: int = 0) -> np.ndarray:
        """
        Apply zero-phase forward-backward Butterworth low-pass filter along the temporal axis.
        Eliminates high-frequency multipath noise while preserving gesture dynamics.
        """
        time_len = data.shape[axis]
        # filtfilt requires sequence length > 3 * max(len(b), len(a))
        padlen = 3 * max(len(self.b_filter), len(self.a_filter))
        if time_len <= padlen:
            # Fallback to simple moving average if sequence is too short
            window = min(3, time_len)
            kernel = np.ones(window) / window
            return np.apply_along_axis(lambda m: np.convolve(m, kernel, mode="same"), axis=axis, arr=data)

        try:
            return signal.filtfilt(self.b_filter, self.a_filter, data, axis=axis).astype(np.float32)
        except Exception:
            # Fallback to single-pass lfilter
            return signal.lfilter(self.b_filter, self.a_filter, data, axis=axis).astype(np.float32)

    # --------------------------------------------------------------------------
    # 4. Outlier Removal (Hampel Filter)
    # --------------------------------------------------------------------------
    def remove_outliers(self, data: np.ndarray) -> np.ndarray:
        """
        Apply Hampel identifier (median absolute deviation) along temporal dimension
        to replace transient noise spikes with local median values.
        """
        filtered = data.copy()
        k = self.hampel_window // 2
        t_len = data.shape[0]

        if t_len <= self.hampel_window:
            return filtered

        for t in range(k, t_len - k):
            window_slice = data[t - k : t + k + 1]
            med = np.median(window_slice, axis=0)
            mad = np.median(np.abs(window_slice - med), axis=0)
            sigma = 1.4826 * mad
            diff = np.abs(data[t] - med)
            mask = diff > (self.hampel_n_sigmas * sigma)
            filtered[t] = np.where(mask, med, data[t])

        return filtered.astype(np.float32)

    # --------------------------------------------------------------------------
    # 5. Normalization (Z-score or Min-Max)
    # --------------------------------------------------------------------------
    def normalize(self, data: np.ndarray) -> np.ndarray:
        """
        Normalize CSI amplitude across temporal and subcarrier dimensions.
        """
        if self.normalize_method == "zscore":
            mean = np.mean(data)
            std = np.std(data)
            if std > 1e-6:
                return ((data - mean) / std).astype(np.float32)
            return (data - mean).astype(np.float32)

        elif self.normalize_method == "minmax":
            min_val = np.min(data)
            max_val = np.max(data)
            if max_val - min_val > 1e-6:
                return ((data - min_val) / (max_val - min_val)).astype(np.float32)
            return np.zeros_like(data, dtype=np.float32)

        return data.astype(np.float32)

    # --------------------------------------------------------------------------
    # 6. Temporal Resampling
    # --------------------------------------------------------------------------
    def resample_time(self, data: np.ndarray, target_len: Optional[int] = None) -> np.ndarray:
        """
        Resample data along time axis (axis 0) to target_timesteps using linear interpolation.
        Input shape: [TimeSteps, Subcarriers]
        Output shape: [target_timesteps, Subcarriers]
        """
        t_target = target_len or self.target_timesteps
        t_curr = data.shape[0]

        if t_curr == t_target:
            return data.astype(np.float32)

        if t_curr == 1:
            return np.repeat(data, t_target, axis=0).astype(np.float32)

        x_orig = np.linspace(0, 1, t_curr)
        x_new = np.linspace(0, 1, t_target)
        interp_func = interpolate.interp1d(x_orig, data, axis=0, kind="linear", fill_value="extrapolate")
        return interp_func(x_new).astype(np.float32)

    # --------------------------------------------------------------------------
    # 7. Window Segmentation
    # --------------------------------------------------------------------------
    @staticmethod
    def segment_windows(
        data: np.ndarray,
        window_size: int = 50,
        stride: int = 25
    ) -> np.ndarray:
        """
        Slice continuous CSI time stream into fixed sliding windows.
        :param data: Input array [T, S].
        :param window_size: Window length.
        :param stride: Step size between windows.
        :return: Array of shape [NumWindows, window_size, S].
        """
        t_len = data.shape[0]
        if t_len < window_size:
            # Pad to window size
            pad_len = window_size - t_len
            padded = np.pad(data, ((0, pad_len), (0, 0)), mode="edge")
            return padded[np.newaxis, ...]

        windows = []
        for start in range(0, t_len - window_size + 1, stride):
            windows.append(data[start : start + window_size])

        if not windows:
            windows.append(data[:window_size])

        return np.array(windows, dtype=np.float32)

    # --------------------------------------------------------------------------
    # 8. Complete Preprocessing Pipeline
    # --------------------------------------------------------------------------
    def preprocess_sample(
        self,
        raw_csi: np.ndarray,
        source_type: str = "intel5300",
        source_rate_hz: float = 1000.0,
        return_torch: bool = True
    ) -> Union[torch.Tensor, np.ndarray]:
        """
        Execute end-to-end CSI preprocessing pipeline.

        Pipeline steps:
        1. Extract amplitude
        2. Subcarrier alignment via ESP32CSIAdapter
        3. Antenna stream reduction (mean-pooling to 1 antenna)
        4. Transpose to [Time, Subcarriers]
        5. Temporal noise filtering (Butterworth)
        6. Outlier removal (Hampel)
        7. Temporal resampling to target_timesteps
        8. Z-score normalization

        :param raw_csi: Raw complex or amplitude array.
        :param source_type: 'intel5300' (Widar) or 'atheros' (NTU-Fi).
        :param source_rate_hz: Original packet sampling rate.
        :param return_torch: If True, return torch.FloatTensor.
        :return: Array or Tensor of shape [TimeSteps=50, Subcarriers=56/114].
        """
        # Step 1: Extract amplitude
        amp = self.extract_amplitude(raw_csi)

        # Handle different input orientations
        # Widar (Intel 5300): shape typically (T, 30, 3, 1) or (T, 30, 3) or (30, T)
        # NTU-Fi (Atheros): shape typically (342, T) or (3, 114, T)
        if source_type.lower() in ("intel5300", "widar", "widar3"):
            if len(amp.shape) == 4:
                # (T, 30, 3, 1) -> squeeze to (T, 30, 3) -> average antennas -> (T, 30) -> transpose to (30, T)
                amp = np.squeeze(amp, axis=-1)
                amp = np.mean(amp, axis=-1)  # (T, 30)
                amp = amp.T  # (30, T)
            elif len(amp.shape) == 3:
                if amp.shape[1] == 30:
                    # (T, 30, 3)
                    amp = np.mean(amp, axis=-1).T  # (30, T)
                elif amp.shape[0] == 30:
                    # (30, 3, T)
                    amp = np.mean(amp, axis=1)  # (30, T)

            # Subcarrier adaptation (30 -> 56 or 114)
            adapted_subcarriers = self.adapter.intel5300_to_esp32(amp)  # (56, T)
            time_series = adapted_subcarriers.T  # (T, 56)

        elif source_type.lower() in ("atheros", "ntufi", "ntu_fi"):
            if len(amp.shape) == 2 and amp.shape[0] == 342:
                # (342, T) -> reshape to (3, 114, T) -> mean antennas -> (114, T)
                amp = amp.reshape(3, 114, -1)
                amp = np.mean(amp, axis=0)  # (114, T)
            elif len(amp.shape) == 3 and amp.shape[1] == 114:
                amp = np.mean(amp, axis=0)  # (114, T)

            # Subcarrier adaptation
            adapted_subcarriers = self.adapter.atheros_to_esp32(amp)  # (56 or 114, T)
            time_series = adapted_subcarriers.T  # (T, 56/114)

        else:
            time_series = amp if len(amp.shape) == 2 else amp.reshape(-1, self.target_subcarriers)

        # Step 5: Filter noise along time axis
        filtered = self.filter_noise(time_series, axis=0)

        # Step 6: Outlier removal
        clean = self.remove_outliers(filtered)

        # Step 7: Temporal resampling to target_timesteps
        resampled = self.resample_time(clean, target_len=self.target_timesteps)

        # Step 8: Normalization
        normalized = self.normalize(resampled)

        if return_torch:
            return torch.from_numpy(normalized).float()
        return normalized
