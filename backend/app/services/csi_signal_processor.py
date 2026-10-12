import numpy as np
from typing import Tuple, List, Dict

class CSISignalProcessor:
    """
    DSP Signal Processing Engine for Wi-Fi Channel State Information (CSI).
    Implements phase sanitization (SFO/STO removal), Hampel outlier filtering,
    exponential moving average smoothing, Z-score normalization, and Doppler feature extraction.
    """
    def __init__(self, num_subcarriers: int = 64):
        self.num_subcarriers = num_subcarriers
        self.subcarrier_indices = np.arange(num_subcarriers) - (num_subcarriers // 2)

    def unwrap_phase(self, phases: np.ndarray) -> np.ndarray:
        """Unwraps phase angles by replacing absolute jumps greater than pi with 2*pi complement."""
        return np.unwrap(phases)

    def sanitize_phase(self, phases: np.ndarray) -> np.ndarray:
        """
        Removes Sampling Frequency Offset (SFO) and Symbol Timing Offset (STO) linear phase distortion.
        Linear phase model: phi_i = phi_true_i + 2*pi * (k_i / N) * tau + beta
        Performs linear regression slope removal: theta = a * k_i + b
        """
        unwrapped = self.unwrap_phase(phases)
        sc = self.subcarrier_indices
        
        # Fit linear slope: y = a * x + b
        A = np.vstack([sc, np.ones(len(sc))]).T
        slope, intercept = np.linalg.lstsq(A, unwrapped, rcond=None)[0]
        
        # Subtract linear distortion line
        sanitized = unwrapped - (slope * sc + intercept)
        return np.clip(sanitized, -np.pi, np.pi)

    def hampel_filter(self, signal: np.ndarray, window_size: int = 5, n_sigmas: float = 3.0) -> np.ndarray:
        """
        Hampel Filter for outlier spike removal.
        Replaces points differing from local median by more than 3 * MAD with local median.
        """
        filtered = signal.copy()
        n = len(signal)
        k = window_size // 2

        for i in range(k, n - k):
            window = signal[i - k : i + k + 1]
            median = np.median(window)
            mad = np.median(np.abs(window - median))
            threshold = n_sigmas * 1.4826 * mad

            if np.abs(signal[i] - median) > threshold and threshold > 1e-6:
                filtered[i] = median

        return filtered

    def smooth_ema(self, signal: np.ndarray, alpha: float = 0.35) -> np.ndarray:
        """Exponential Moving Average (EMA) smoothing across subcarrier array."""
        smoothed = np.zeros_like(signal)
        smoothed[0] = signal[0]
        for i in range(1, len(signal)):
            smoothed[i] = alpha * signal[i] + (1 - alpha) * smoothed[i - 1]
        return smoothed

    def normalize_zscore(self, amplitudes: np.ndarray) -> np.ndarray:
        """Z-score standardize subcarrier amplitudes: Z = (x - mean) / std."""
        mean = np.mean(amplitudes)
        std = np.std(amplitudes)
        if std < 1e-6:
            return amplitudes - mean
        return (amplitudes - mean) / std

    def process_frame(self, amplitudes: List[float], phases: List[float]) -> Tuple[List[float], List[float], float]:
        """
        Full DSP pipeline execution on a single CSI frame:
        1. Hampel outlier filtering on raw amplitudes
        2. EMA smoothing on amplitudes
        3. Linear phase unwrapping & sanitization on phases
        4. Calculates Doppler variance ratio
        """
        amps_arr = np.array(amplitudes, dtype=np.float32)
        phases_arr = np.array(phases, dtype=np.float32)

        # 1. Clean amplitudes
        clean_amps = self.hampel_filter(amps_arr)
        clean_amps = self.smooth_ema(clean_amps)

        # 2. Sanitize phases
        clean_phases = self.sanitize_phase(phases_arr)

        # 3. Subcarrier Doppler energy variance
        doppler_energy = float(np.var(np.diff(clean_amps)))

        return (
            [round(float(a), 3) for a in clean_amps],
            [round(float(p), 4) for p in clean_phases],
            round(doppler_energy, 3)
        )

csi_dsp = CSISignalProcessor(num_subcarriers=64)
