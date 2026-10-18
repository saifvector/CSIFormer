"""
CSIFormer Phase 15 — Domain Gap Forensic Analysis Script.

Analyzes physical discrepancies between:
1. Real ESP32-S3 captures in data/real_csi_dataset/
2. Training datasets (Widar 3.0 @ 5.825 GHz, NTU-Fi @ Atheros 5 GHz)

Generates:
- reports/phase15_domain_gap_analysis.png
- reports/phase15_domain_gap_metrics.json
"""

import sys
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR / "backend"))

from app.services.physics_csi_preprocessor import PhysicsCSIPreprocessor

DATASET_DIR = BASE_DIR / "data" / "real_csi_dataset"
REPORTS_DIR = BASE_DIR / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

def main():
    print("=" * 80)
    print("PHASE 15 — PHYSICAL DOMAIN GAP FORENSIC ANALYSIS")
    print("=" * 80)

    # 1. Load real ESP32-S3 sessions
    manifest_path = DATASET_DIR / "dataset_manifest.json"
    with open(manifest_path, "r") as f:
        manifest = json.load(f)

    sessions = manifest["sessions"]
    print(f"Loaded {len(sessions)} real sessions from manifest.")

    # Aggregate timestamp intervals and RSSI
    all_dt = []
    all_rssi = []
    real_matrices = []

    for s in sessions:
        json_path = DATASET_DIR / s["json_file"]
        with open(json_path, "r") as f:
            data = json.load(f)
        frames = data["frames"]
        if len(frames) < 2:
            continue
        ts = np.array([fr["timestamp"] for fr in frames])
        dt = np.diff(ts)
        all_dt.extend(dt[dt > 0].tolist())
        all_rssi.extend([fr["rssi"] for fr in frames])
        
        # Load amplitude matrix [T, 56]
        mat = np.array([fr["amplitudes"] for fr in frames], dtype=np.float32)
        real_matrices.append(mat)

    all_dt = np.array(all_dt)
    mean_dt = float(np.mean(all_dt))
    std_dt = float(np.std(all_dt))
    effective_fs = 1.0 / mean_dt if mean_dt > 0 else 35.0
    jitter_pct = (std_dt / mean_dt) * 100.0

    print(f"\n[Hardware Timing Telemetry]")
    print(f"  Mean Inter-Packet Interval (dt): {mean_dt*1000.0:.2f} ms")
    print(f"  Jitter Std Dev (sigma_dt): {std_dt*1000.0:.2f} ms ({jitter_pct:.1f}%)")
    print(f"  Effective Hardware Sampling Rate: {effective_fs:.2f} Hz")
    print(f"  Nyquist Frequency (f_Nyquist = fs / 2): {effective_fs / 2.0:.2f} Hz")

    # 2. Physics Doppler Aliasing & Frequency Scaling Analysis
    c = 3.0e8
    f_esp = 2.442e9
    lambda_esp = c / f_esp # 0.1228 m
    f_widar = 5.825e9
    lambda_widar = c / f_widar # 0.0515 m
    doppler_ratio = f_widar / f_esp # 2.385

    v_nyquist_esp = (effective_fs / 2.0) * lambda_esp / 2.0
    v_nyquist_widar = (1000.0 / 2.0) * lambda_widar / 2.0

    print(f"\n[Physics Doppler & Kinematic Scale Comparison]")
    print(f"  Widar 3.0 Wavelength: {lambda_widar*100.0:.2f} cm | ESP32-S3: {lambda_esp*100.0:.2f} cm")
    print(f"  Carrier Frequency Ratio (f_widar / f_esp): {doppler_ratio:.3f}x")
    print(f"  Max Unaliased Velocity (ESP32-S3 @ {effective_fs:.1f} Hz): {v_nyquist_esp:.2f} m/s ({v_nyquist_esp*3.6:.1f} km/h)")
    print(f"  Max Unaliased Velocity (Widar 3.0 @ 1000 Hz): {v_nyquist_widar:.2f} m/s ({v_nyquist_widar*3.6:.1f} km/h)")

    # 3. Frequency & Subcarrier Interpolation Artifacts
    # Compare raw real 5-tone interpolated matrix vs ideal smooth OFDM profile
    prep = PhysicsCSIPreprocessor(carrier_freq=2.442e9, source_rate_hz=effective_fs, target_timesteps=50, target_channels=56)
    sample_real_win = real_matrices[0][:50, :56] # [50, 56]
    doppler_real = prep.compute_doppler_spectrogram(sample_real_win)

    # 4. Generate Comprehensive 4-Panel Visualization
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    # Panel A: Hardware Inter-Packet Arrival Time Distribution
    ax = axes[0, 0]
    ax.hist(all_dt * 1000.0, bins=40, color="#1f77b4", edgecolor="black", alpha=0.8)
    ax.axvline(mean_dt * 1000.0, color="red", linestyle="--", linewidth=2, label=f"Mean: {mean_dt*1000.0:.1f} ms ({effective_fs:.1f} Hz)")
    ax.set_title("ESP32-S3 Real Inter-Packet Interval (dt)", fontsize=12, fontweight="bold")
    ax.set_xlabel("Time Delta (ms)")
    ax.set_ylabel("Packet Count")
    ax.legend()
    ax.grid(True, linestyle=":", alpha=0.6)

    # Panel B: Subcarrier Amplitude Profiles (Tone Interpolation Artifacts)
    ax = axes[0, 1]
    for i in range(min(5, len(sample_real_win))):
        ax.plot(np.arange(56), sample_real_win[i], label=f"Frame t={i+1}")
    ax.set_title("ESP32-S3 Real 56-Subcarrier Amplitude (5-Tone Interpolated)", fontsize=12, fontweight="bold")
    ax.set_xlabel("Subcarrier Index (0 to 55)")
    ax.set_ylabel("Amplitude")
    ax.legend(loc="upper right", fontsize=8)
    ax.grid(True, linestyle=":", alpha=0.6)

    # Panel C: Doppler Shift Scaling (Widar 5.8 GHz vs ESP32-S3 2.4 GHz)
    ax = axes[1, 0]
    vel_range = np.linspace(0, 3.0, 100) # 0 to 3 m/s human velocity
    f_d_widar = 2 * vel_range / lambda_widar
    f_d_esp = 2 * vel_range / lambda_esp
    ax.plot(vel_range, f_d_widar, "b-", linewidth=2.5, label="Widar 3.0 (5.825 GHz): 38.8 Hz/(m/s)")
    ax.plot(vel_range, f_d_esp, "r-", linewidth=2.5, label="ESP32-S3 (2.442 GHz): 16.3 Hz/(m/s)")
    ax.axhline(effective_fs / 2.0, color="black", linestyle="--", linewidth=1.5, label=f"ESP32-S3 Nyquist Limit ({effective_fs/2:.1f} Hz)")
    ax.axvspan(v_nyquist_esp, 3.0, color="orange", alpha=0.2, label="Aliasing Region (ESP32-S3)")
    ax.set_title("Kinematic Doppler Shift Scaling & Nyquist Aliasing", fontsize=12, fontweight="bold")
    ax.set_xlabel("Human Limb / Torso Velocity (m/s)")
    ax.set_ylabel("Doppler Frequency Shift (Hz)")
    ax.legend(loc="upper left", fontsize=9)
    ax.grid(True, linestyle=":", alpha=0.6)

    # Panel D: Real Doppler Spectrogram (DFS) on Hardware Capture
    ax = axes[1, 1]
    im = ax.imshow(doppler_real.T, aspect="auto", cmap="inferno", origin="lower",
                   extent=[0, 50, -effective_fs/2.0, effective_fs/2.0])
    ax.set_title("Real ESP32-S3 Doppler DFS Spectrogram [50, 56]", fontsize=12, fontweight="bold")
    ax.set_xlabel("Temporal Frame (0 to 50)")
    ax.set_ylabel("Doppler Frequency (Hz)")
    fig.colorbar(im, ax=ax, label="Normalized Spectral Power (dB)")

    plt.tight_layout()
    viz_path = REPORTS_DIR / "phase15_domain_gap_analysis.png"
    plt.savefig(viz_path, dpi=300)
    plt.close()
    print(f"\n[Artifact] Saved domain gap visualization: {viz_path}")

    # Export Metrics JSON
    metrics_payload = {
        "hardware_telemetry": {
            "mean_dt_ms": round(mean_dt * 1000.0, 2),
            "std_dt_ms": round(std_dt * 1000.0, 2),
            "effective_sampling_rate_hz": round(effective_fs, 2),
            "jitter_percent": round(jitter_pct, 2),
            "mean_rssi_dbm": round(float(np.mean(all_rssi)), 2),
            "total_packets_analyzed": len(all_dt)
        },
        "physics_parameters": {
            "carrier_frequency_esp_ghz": 2.442,
            "carrier_frequency_widar_ghz": 5.825,
            "wavelength_esp_m": round(lambda_esp, 4),
            "wavelength_widar_m": round(lambda_widar, 4),
            "doppler_scale_ratio": round(doppler_ratio, 3),
            "nyquist_limit_esp_hz": round(effective_fs / 2.0, 2),
            "max_unaliased_velocity_esp_ms": round(v_nyquist_esp, 2),
            "nyquist_limit_widar_hz": 500.0,
            "max_unaliased_velocity_widar_ms": round(v_nyquist_widar, 2)
        },
        "domain_discrepancy_verdicts": {
            "doppler_compression": f"ESP32-S3 Doppler frequencies are {doppler_ratio:.2f}x smaller than Widar training data",
            "aliasing_risk": f"Velocities above {v_nyquist_esp:.2f} m/s alias into lower frequency bins on ESP32-S3",
            "spatial_subcarriers": "Running firmware outputs 5 subcarrier tones linearly interpolated to 56 tones",
            "representation_compatibility": "Direct feed into unmodified Phase 13 model experiences scale and tone distortion"
        }
    }

    metrics_path = REPORTS_DIR / "phase15_domain_gap_metrics.json"
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(metrics_payload, f, indent=2)
    print(f"[Artifact] Saved domain gap metrics: {metrics_path}")


if __name__ == "__main__":
    main()
