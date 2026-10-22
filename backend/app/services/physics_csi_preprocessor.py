"""
Physics-Aware CSI Preprocessing Engine for CSIFormer.

Implements signal-level physical decomposition:
1. Raw Amplitude and Raw Phase Extraction
2. Phase Sanitization (Unwrapping + Linear Slope Detrending for STO/SFO removal)
3. Cross-Antenna Conjugate Multiplication (Hardware CFO & Time-Offset Cancellation)
4. Static Multipath & Torso Reflection Subtraction (DC Notch / Background Filtering)
5. Subcarrier Energy Normalization (Mitigates Frequency-Selective Body Resonance)
6. Doppler Frequency Spectrum (DFS) & Velocity Profile Extraction via STFT
7. Fixed Shape Tensor Formatting: [TimeSteps=50, Channels=56] for Zero-Overhead CSIFormer Execution
"""

from typing import Dict, Any, Optional, Tuple, Union
import numpy as np
import scipy.signal as signal
from scipy import interpolate
import torch


class PhysicsCSIPreprocessor:
    """
    Production-grade Physics-Aware Wi-Fi CSI Preprocessor.
    Decomposes and normalizes raw complex CSI at the electromagnetic signal level.
    """

    SPEED_OF_LIGHT = 299792458.0  # m/s

    def __init__(
        self,
        carrier_freq: float = 5.2e9,     # 5.2 GHz (Widar 3.0 / 802.11a/n/ac)
        source_rate_hz: float = 1000.0,  # 1000 Hz packet rate
        target_timesteps: int = 50,      # CSIFormer temporal dimension
        target_channels: int = 56,       # CSIFormer spatial/channel dimension (HT20)
        stft_window: int = 64,
        stft_noverlap: int = 48,
        stft_nfft: int = 128
    ):
        self.carrier_freq = carrier_freq
        self.wavelength = self.SPEED_OF_LIGHT / carrier_freq  # ~0.0576 m
        self.source_rate_hz = source_rate_hz
        self.target_timesteps = target_timesteps
        self.target_channels = target_channels
        self.stft_window = stft_window
        self.stft_noverlap = stft_noverlap
        self.stft_nfft = stft_nfft

    # =========================================================================
    # 1. Component Extraction
    # =========================================================================
    @staticmethod
    def extract_raw_amplitude(csi: np.ndarray) -> np.ndarray:
        """Extract magnitude: |H(t, k)|."""
        if np.iscomplexobj(csi):
            return np.abs(csi).astype(np.float32)
        return np.asarray(csi, dtype=np.float32)

    @staticmethod
    def extract_raw_phase(csi: np.ndarray) -> np.ndarray:
        """Extract raw phase angle: angle(H(t, k)) in radians."""
        if np.iscomplexobj(csi):
            return np.angle(csi).astype(np.float32)
        return np.zeros_like(csi, dtype=np.float32)

    # =========================================================================
    # 2. Phase Sanitization (Unwrapping + Linear Trend Removal)
    # =========================================================================
    @staticmethod
    def sanitize_phase(raw_phase: np.ndarray) -> np.ndarray:
        """
        Sanitize raw CSI phase:
        1. Unwrap phase across subcarriers to remove 2*pi branch cuts.
        2. Fit linear regression line across subcarrier indices to eliminate
           linear phase ramp induced by Sampling Time Offset (STO) and Carrier Frequency Offset (CFO).

        Input shape: (T, num_subcarriers) or (num_subcarriers, T).
        Returns sanitized phase of identical shape.
        """
        transposed = False
        if raw_phase.ndim == 2 and raw_phase.shape[0] < raw_phase.shape[1]:
            raw_phase = raw_phase.T
            transposed = True

        unwrapped = np.unwrap(raw_phase, axis=-1)
        num_subcarriers = unwrapped.shape[-1]
        k_idx = np.arange(num_subcarriers, dtype=np.float32)
        k_centered = k_idx - np.mean(k_idx)
        denom = np.sum(k_centered ** 2)

        if denom < 1e-8:
            return unwrapped.T if transposed else unwrapped

        slopes = np.sum(unwrapped * k_centered[None, :], axis=-1, keepdims=True) / denom
        offsets = np.mean(unwrapped, axis=-1, keepdims=True)
        linear_fit = offsets + slopes * k_centered[None, :]

        sanitized = unwrapped - linear_fit
        return sanitized.T.astype(np.float32) if transposed else sanitized.astype(np.float32)

    # =========================================================================
    # 3. Cross-Antenna Conjugate Multiplication (Differential Phase)
    # =========================================================================
    @staticmethod
    def cross_antenna_conjugate(csi_multi_rx: np.ndarray) -> np.ndarray:
        """
        Compute cross-antenna conjugate multiplication:
        S_{i, j}(t, k) = H_i(t, k) * conj(H_j(t, k))

        This mathematically cancels packet-level Carrier Frequency Offset (CFO),
        Sampling Frequency Offset (SFO), and initial random phase offsets common to both RX antennas.
        """
        if csi_multi_rx.ndim == 4:
            csi_multi_rx = csi_multi_rx[:, :, :, 0]

        if csi_multi_rx.shape[-1] >= 2:
            ant1 = csi_multi_rx[:, :, 0]
            ant2 = csi_multi_rx[:, :, 1]
            return ant1 * np.conj(ant2)
        elif csi_multi_rx.shape[-1] == 1:
            return csi_multi_rx[:, :, 0]
        return csi_multi_rx

    # =========================================================================
    # 4. Static Component Removal (DC Subtraction / Torso Filtering)
    # =========================================================================
    @staticmethod
    def remove_static_component(complex_csi: np.ndarray, method: str = "mean") -> np.ndarray:
        """
        Subtract static multipath reflections (walls, floor) and static torso reflections.
        Leaves only dynamic Doppler reflections from limb and gesture motion.
        """
        if method == "mean":
            static_comp = np.mean(complex_csi, axis=0, keepdims=True)
        elif method == "median":
            static_comp = np.median(complex_csi.real, axis=0, keepdims=True) + 1j * np.median(complex_csi.imag, axis=0, keepdims=True)
        elif method == "hanning_highpass":
            t_len = complex_csi.shape[0]
            if t_len > 16:
                b, a = signal.butter(2, 0.05, btype="highpass")
                real_filt = signal.filtfilt(b, a, complex_csi.real, axis=0)
                imag_filt = signal.filtfilt(b, a, complex_csi.imag, axis=0)
                return (real_filt + 1j * imag_filt).astype(np.complex64)
            static_comp = np.mean(complex_csi, axis=0, keepdims=True)
        else:
            static_comp = np.mean(complex_csi, axis=0, keepdims=True)

        return (complex_csi - static_comp).astype(np.complex64)

    # =========================================================================
    # 5. Subcarrier Energy Normalization
    # =========================================================================
    @staticmethod
    def normalize_subcarrier_energy(csi_data: np.ndarray) -> np.ndarray:
        """
        Normalize each subcarrier channel by its root-mean-square energy.
        Eliminates frequency-selective body resonance and static user gain differences.
        """
        rms = np.sqrt(np.mean(np.abs(csi_data) ** 2, axis=0, keepdims=True) + 1e-8)
        return (csi_data / rms).astype(csi_data.dtype)

    # =========================================================================
    # 6. Doppler Frequency Spectrum (DFS) & Velocity Profile Extraction
    # =========================================================================
    def compute_doppler_spectrogram(
        self,
        complex_csi: np.ndarray,
        remove_static: bool = True
    ) -> np.ndarray:
        """
        Extract Doppler Frequency Spectrum (DFS) using Short-Time Fourier Transform (STFT).
        """
        if complex_csi.ndim == 4:
            if complex_csi.shape[2] >= 2:
                complex_csi = complex_csi[:, :, 0, 0] * np.conj(complex_csi[:, :, 1, 0])
            else:
                complex_csi = complex_csi[:, :, 0, 0]
        elif complex_csi.ndim == 3:
            if complex_csi.shape[-1] >= 2:
                complex_csi = complex_csi[:, :, 0] * np.conj(complex_csi[:, :, 1])
            else:
                complex_csi = complex_csi[:, :, 0]

        T_len, num_sub = complex_csi.shape

        if remove_static:
            dynamic_csi = self.remove_static_component(complex_csi, method="mean")
        else:
            dynamic_csi = complex_csi

        window_size = min(self.stft_window, T_len)
        if window_size < 8:
            return np.zeros((self.target_timesteps, self.target_channels), dtype=np.float32)

        noverlap = min(self.stft_noverlap, window_size - 1)
        nfft = max(self.stft_nfft, window_size)

        spectrogram_accum = None
        for k in range(num_sub):
            f, t, Zxx = signal.stft(
                dynamic_csi[:, k],
                fs=self.source_rate_hz,
                window="hann",
                nperseg=window_size,
                noverlap=noverlap,
                nfft=nfft,
                return_onesided=False
            )
            Zxx_shifted = np.fft.fftshift(Zxx, axes=0)
            power = np.abs(Zxx_shifted) ** 2

            if spectrogram_accum is None:
                spectrogram_accum = power
            else:
                spectrogram_accum += power

        spectrogram_avg = spectrogram_accum / num_sub
        dfs_log = 10.0 * np.log10(spectrogram_avg + 1e-8)
        dfs_time_first = dfs_log.T

        t_src = np.linspace(0, 1, dfs_time_first.shape[0])
        f_src = np.linspace(0, 1, dfs_time_first.shape[1])
        t_dst = np.linspace(0, 1, self.target_timesteps)
        f_dst = np.linspace(0, 1, self.target_channels)

        interp_2d = interpolate.RectBivariateSpline(t_src, f_src, dfs_time_first)
        resampled_dfs = interp_2d(t_dst, f_dst).astype(np.float32)

        mean_val = np.mean(resampled_dfs)
        std_val = np.std(resampled_dfs)
        if std_val > 1e-6:
            resampled_dfs = (resampled_dfs - mean_val) / std_val

        return resampled_dfs

    # =========================================================================
    # 7. Adapters for Candidate Representations
    # =========================================================================
    def process_raw_representation(self, raw_csi: np.ndarray) -> torch.Tensor:
        """Candidate 1: Standard Amplitude (Baseline). Shape: [50, 56]"""
        amp = self.extract_raw_amplitude(raw_csi)
        if amp.ndim == 4:
            amp = np.mean(amp[:, :, :, 0], axis=-1)
        elif amp.ndim == 3:
            amp = np.mean(amp, axis=-1)

        t_len = amp.shape[0]
        interp_sub = interpolate.interp1d(
            np.linspace(0, 1, amp.shape[1]),
            amp,
            axis=1,
            kind="linear",
            fill_value="extrapolate"
        )
        amp_56 = interp_sub(np.linspace(0, 1, self.target_channels))

        interp_time = interpolate.interp1d(
            np.linspace(0, 1, t_len),
            amp_56,
            axis=0,
            kind="linear",
            fill_value="extrapolate"
        )
        resampled = interp_time(np.linspace(0, 1, self.target_timesteps)).astype(np.float32)

        resampled = (resampled - np.mean(resampled)) / (np.std(resampled) + 1e-8)
        return torch.from_numpy(resampled.astype(np.float32))

    def process_phase_sanitized_representation(self, raw_csi: np.ndarray) -> torch.Tensor:
        """Candidate 2: Static-Subtracted + Sanitized Phase. Shape: [50, 56]"""
        if raw_csi.ndim == 4 and raw_csi.shape[2] >= 2:
            conj_csi = raw_csi[:, :, 0, 0] * np.conj(raw_csi[:, :, 1, 0])
        elif raw_csi.ndim == 4:
            conj_csi = raw_csi[:, :, 0, 0]
        else:
            conj_csi = raw_csi

        dyn_csi = self.remove_static_component(conj_csi, method="mean")
        dyn_phase = self.extract_raw_phase(dyn_csi)
        sanitized = self.sanitize_phase(dyn_phase)

        dyn_amp = self.extract_raw_amplitude(dyn_csi)
        norm_dyn = self.normalize_subcarrier_energy(dyn_amp)
        physics_feat = norm_dyn * np.cos(sanitized)

        t_len = physics_feat.shape[0]
        interp_sub = interpolate.interp1d(
            np.linspace(0, 1, physics_feat.shape[1]),
            physics_feat,
            axis=1,
            kind="linear",
            fill_value="extrapolate"
        )
        feat_56 = interp_sub(np.linspace(0, 1, self.target_channels))

        interp_time = interpolate.interp1d(
            np.linspace(0, 1, t_len),
            feat_56,
            axis=0,
            kind="linear",
            fill_value="extrapolate"
        )
        resampled = interp_time(np.linspace(0, 1, self.target_timesteps)).astype(np.float32)

        resampled = (resampled - np.mean(resampled)) / (np.std(resampled) + 1e-8)
        return torch.from_numpy(resampled.astype(np.float32))

    def process_doppler_representation(self, raw_csi: np.ndarray) -> torch.Tensor:
        """Candidate 3: Doppler Frequency Spectrum (DFS) / Velocity Profile. Shape: [50, 56]"""
        dfs = self.compute_doppler_spectrogram(raw_csi, remove_static=True)
        return torch.from_numpy(dfs.astype(np.float32))


class CalibratedPhysicsPreprocessor(PhysicsCSIPreprocessor):
    """
    Extends PhysicsCSIPreprocessor with carrier frequency scaling correction
    (2.385x Doppler scale expansion for 2.442 GHz -> 5.825 GHz equivalence).
    """
    def __init__(
        self,
        carrier_freq: float = 2.442e9,
        source_rate_hz: float = 35.58,
        target_timesteps: int = 50,
        target_channels: int = 56,
        stft_window: int = 64,
        stft_noverlap: int = 48,
        stft_nfft: int = 128,
        doppler_scale: Optional[float] = None
    ):
        super().__init__(
            carrier_freq=carrier_freq,
            source_rate_hz=source_rate_hz,
            target_timesteps=target_timesteps,
            target_channels=target_channels,
            stft_window=stft_window,
            stft_noverlap=stft_noverlap,
            stft_nfft=stft_nfft
        )
        self.doppler_scale = doppler_scale if doppler_scale is not None else (5.825 / 2.442)  # 2.385x scaling

    def compute_doppler_spectrogram(self, csi_amplitude: np.ndarray, remove_static: bool = True) -> np.ndarray:
        # Standard STFT
        base_dopp = super().compute_doppler_spectrogram(csi_amplitude, remove_static=remove_static)  # [50, 56]
        
        # Rescale the Doppler frequency bins (axis 1) by interpolating around DC center
        n_time, n_freq = base_dopp.shape
        center = n_freq // 2
        f_old = np.arange(n_freq) - center
        f_new = f_old / self.doppler_scale  # Stretch frequencies back to 5.8 GHz scale
        
        rescaled_dopp = np.zeros_like(base_dopp)
        for t in range(n_time):
            rescaled_dopp[t] = np.interp(f_old, f_new, base_dopp[t])
        
        return rescaled_dopp.astype(np.float32)

