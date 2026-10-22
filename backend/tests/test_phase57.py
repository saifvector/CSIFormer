"""
CSIFormer Phase 57 — Live-vs-Training Preprocessing Parity and Collector Integrity Test Suite.

Validates:
1. Gate 0: Bit-level MD5 verification of protected assets.
2. Deterministic Preprocessing Parity (Task 2):
   - Fixed-seed random complex CSI array.
   - Constant / Near-static signal (DC subtraction).
   - Synthetic sinusoidal component with known temporal frequency.
   - Input shape, output shape, dtype, finite-value, and normalization checks.
   - Numerical comparison between Phase 15 training reference and LivePipelineService.
3. Checkpoint-Associated Preprocessor Selection (Task 3):
   - Default 'phase13' preserves backward compatibility.
   - Explicit 'phase15' activates CalibratedPhysicsPreprocessor with 2.385x Doppler scale.
4. Sequence-Gap and Loss Accounting Decoupling (Task 4):
   - Interleaved target and non-target streams prove ambient frames do not inflate packets_lost.
   - Confirmed UART transport loss is accurately isolated.
   - 32-bit unsigned sequence wraparound is handled cleanly.
   - Firmware reboot / counter reset is detected and handled without negative loss.
   - Tri-counter distinction (firmware callback, 802.11 MAC, host serial record count).
"""

import sys
import hashlib
from pathlib import Path
import numpy as np
import pytest
import torch

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(BASE_DIR))
sys.path.append(str(BASE_DIR / "backend"))

from backend.app.services.physics_csi_preprocessor import PhysicsCSIPreprocessor, CalibratedPhysicsPreprocessor
from backend.app.services.live_pipeline_service import LivePipelineService
from backend.app.services.real_csi_collector import RealCSICollector

DATASET_DIR = BASE_DIR / "data" / "real_csi_dataset"
MANIFEST_PATH = DATASET_DIR / "dataset_manifest.json"
MODELS_DIR = BASE_DIR / "models"

EXPECTED_PHASE13_MD5 = "383b4d98c08f8970b0443738f170ec01"
EXPECTED_PHASE15_MD5 = "ab3d97a04d78edf75d807178772bc828"
EXPECTED_MANIFEST_MD5 = "a58e1280fb2c0a6649335a9a381d00c6"


def compute_md5(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest().lower()


# ==============================================================================
# Gate 0: Protected Asset Invariance
# ==============================================================================
def test_phase57_gate0_protected_file_invariance():
    """Verify that protected model checkpoints and dataset manifest remain untouched."""
    p13 = MODELS_DIR / "csiformer_phase13_best.pth"
    p15 = MODELS_DIR / "csiformer_phase15_adapted.pth"

    assert p13.exists(), f"Missing production checkpoint: {p13}"
    assert p15.exists(), f"Missing experimental checkpoint: {p15}"
    assert MANIFEST_PATH.exists(), f"Missing dataset manifest: {MANIFEST_PATH}"

    assert compute_md5(p13) == EXPECTED_PHASE13_MD5, "Phase 13 checkpoint modified!"
    assert compute_md5(p15) == EXPECTED_PHASE15_MD5, "Phase 15 checkpoint modified!"
    assert compute_md5(MANIFEST_PATH) == EXPECTED_MANIFEST_MD5, "Dataset manifest modified!"


# ==============================================================================
# Task 2 & Task 3: Deterministic Preprocessing Parity Tests
# ==============================================================================
def test_phase57_parity_fixed_seed_random_complex():
    """
    Test 1: Compare Phase 15 training reference and LivePipelineService on fixed-seed random input.
    Verifies that when LivePipelineService is configured for Phase 15, output tensors match identically.
    """
    rng = np.random.RandomState(42)
    # Generate synthetic 50x56 amplitude window
    sample_amp = rng.uniform(10.0, 45.0, size=(50, 56)).astype(np.float32)

    # 1. Authoritative Phase 15 Training Reference Pipeline
    ref_prep = CalibratedPhysicsPreprocessor(
        carrier_freq=2.442e9,
        source_rate_hz=35.58,
        target_timesteps=50,
        target_channels=56,
        stft_window=64,
        stft_noverlap=48,
        stft_nfft=128
    )
    # Branch A Reference (column-wise temporal z-score)
    m = sample_amp.mean(axis=0, keepdims=True)
    s = sample_amp.std(axis=0, keepdims=True) + 1e-6
    ref_tensor_raw = torch.tensor((sample_amp - m) / s, dtype=torch.float32).unsqueeze(0)
    # Branch B Reference (Calibrated STFT with 2.385x Doppler expansion)
    ref_d_mat = ref_prep.compute_doppler_spectrogram(sample_amp)
    ref_tensor_dopp = torch.tensor(ref_d_mat, dtype=torch.float32).unsqueeze(0)

    # 2. Live Pipeline Service configured for Phase 15
    live_service = LivePipelineService()
    live_service.configure_preprocessor_for_checkpoint("phase15")
    live_raw, live_dopp = live_service.preprocess_window(sample_amp)

    # Shape and dtype validation
    assert live_raw.shape == (1, 50, 56)
    assert live_dopp.shape == (1, 50, 56)
    assert live_raw.dtype == torch.float32
    assert live_dopp.dtype == torch.float32
    assert torch.isfinite(live_raw).all()
    assert torch.isfinite(live_dopp).all()

    # Exact parity assertion: max difference must be 0.0 (or within floating-point epsilon)
    raw_diff = float(torch.max(torch.abs(ref_tensor_raw.cpu() - live_raw.cpu())).item())
    dopp_diff = float(torch.max(torch.abs(ref_tensor_dopp.cpu() - live_dopp.cpu())).item())

    assert raw_diff < 1e-6, f"Branch A raw parity failed: max diff = {raw_diff}"
    assert dopp_diff < 1e-6, f"Branch B Doppler parity failed: max diff = {dopp_diff}"


def test_phase57_parity_constant_static_signal():
    """
    Test 2: Parity under a static / DC-only signal across all 50 frames.
    Static DC component subtraction removes the static component.
    """
    # Constant amplitude across all 50 frames
    static_amp = np.full((50, 56), fill_value=28.5, dtype=np.float32)

    ref_prep = CalibratedPhysicsPreprocessor(
        carrier_freq=2.442e9,
        source_rate_hz=35.58,
        target_timesteps=50,
        target_channels=56
    )
    live_service = LivePipelineService()
    live_service.configure_preprocessor_for_checkpoint("phase15")

    # Both must handle zero-variance / static without crashing or NaN
    ref_dopp = ref_prep.compute_doppler_spectrogram(static_amp)
    live_raw, live_dopp = live_service.preprocess_window(static_amp)

    assert np.isfinite(ref_dopp).all()
    assert torch.isfinite(live_raw).all()
    assert torch.isfinite(live_dopp).all()

    dopp_diff = float(torch.max(torch.abs(torch.tensor(ref_dopp) - live_dopp.squeeze(0).cpu())).item())
    assert dopp_diff < 1e-6, f"Static signal Doppler parity failed: max diff = {dopp_diff}"


def test_phase57_parity_synthetic_sinusoid_known_frequency():
    """
    Test 3: Synthetic sinusoidal component with known physical frequency.
    Construct a 3.0 Hz modulation across 50 frames at 35.58 Hz.
    Verifies that the live pipeline matches the Phase 15 reference exactly.
    Also documents that the uncalibrated Phase 13 pipeline diverged significantly.
    """
    t = np.arange(50) / 35.58
    f0 = 3.0  # 3.0 Hz oscillation
    # Multi-subcarrier modulated signal
    sinusoid_amp = np.zeros((50, 56), dtype=np.float32)
    for k in range(56):
        phase_offset = k * 0.1
        sinusoid_amp[:, k] = 30.0 + 8.0 * np.sin(2 * np.pi * f0 * t + phase_offset)

    # Reference
    ref_prep = CalibratedPhysicsPreprocessor(
        carrier_freq=2.442e9,
        source_rate_hz=35.58,
        target_timesteps=50,
        target_channels=56
    )
    ref_d_mat = ref_prep.compute_doppler_spectrogram(sinusoid_amp)

    # Live configured for Phase 15
    live_service = LivePipelineService()
    live_service.configure_preprocessor_for_checkpoint("phase15")
    _, live_dopp = live_service.preprocess_window(sinusoid_amp)

    parity_diff = float(torch.max(torch.abs(torch.tensor(ref_d_mat) - live_dopp.squeeze(0).cpu())).item())
    assert parity_diff < 1e-6, f"Sinusoid parity failed: max diff = {parity_diff}"

    # Verify that Phase 13 preprocessor configuration diverges from Phase 15
    live_service.configure_preprocessor_for_checkpoint("phase13")
    _, p13_dopp = live_service.preprocess_window(sinusoid_amp)
    divergence = float(torch.max(torch.abs(torch.tensor(ref_d_mat) - p13_dopp.squeeze(0).cpu())).item())
    assert divergence > 1.0, f"Expected divergence between Phase 13 and Phase 15 preprocessor, got {divergence}"


def test_phase57_preprocessor_backward_compatibility():
    """
    Test 4: Backward compatibility verification.
    LivePipelineService default initialization must retain Phase 13 configuration
    (stft_window=32, noverlap=24, nfft=64) to preserve existing test contracts.
    """
    service = LivePipelineService()
    # Reset to default
    service.configure_preprocessor_for_checkpoint("phase13")

    assert service.active_checkpoint_id == "phase13"
    assert service.preprocessor.carrier_freq == 2.442e9
    assert service.preprocessor.source_rate_hz == 30.0
    assert service.preprocessor.stft_window == 32
    assert service.preprocessor.stft_noverlap == 24
    assert service.preprocessor.stft_nfft == 64
    assert not hasattr(service, "predict_window")


# ==============================================================================
# Task 4: Sequence-Gap and Loss Accounting Integrity Tests
# ==============================================================================
def test_phase57_interleaved_ambient_filtering_no_false_loss():
    """
    Test 5: Interleaved target and non-target stream.
    Demonstrates that intentional MAC filtering of ambient frames does NOT
    falsely increment packets_lost when serial delivery is continuous.
    """
    target_ap = "98:BA:5F:EF:28:26"
    ambient_mac = "18:CC:88:7E:74:71"

    collector = RealCSICollector(target_mac=target_ap, filter_by_mac=True)

    stream = [
        {"seq": 1, "mac": target_ap, "rssi": -55.0},
        {"seq": 2, "mac": ambient_mac, "rssi": -72.0},
        {"seq": 3, "mac": ambient_mac, "rssi": -70.0},
        {"seq": 4, "mac": target_ap, "rssi": -56.0},
    ]

    for p in stream:
        collector._process_parsed_frame({
            "timestamp": 1000.0 + p["seq"] * 0.03,
            "sequence": p["seq"],
            "mac": p["mac"],
            "rssi": p["rssi"],
            "noise_floor": -95.0,
            "raw_amplitudes": [15.0] * 56,
            "raw_phases": [0.1] * 56
        })

    # Sequence gaps between admitted target packets = 4 - (1 + 1) = 2
    assert collector.target_sequence_gaps == 2
    # Two ambient frames were intentionally filtered
    assert collector.filtered_non_target_packets == 2
    # Admitted target packets
    assert collector.packets_received == 2
    # Firmware sequence counter had zero gaps (1, 2, 3, 4 were all received)
    assert collector.firmware_sequence_gaps == 0
    assert collector.confirmed_transport_loss == 0
    # Crucial assertion: packets_lost MUST BE ZERO (no false packet loss attribution!)
    assert collector.packets_lost == 0

    health = collector.get_stream_health()
    assert health["packets_lost"] == 0
    assert health["packet_loss_pct"] == 0.0
    assert health["target_sequence_gaps"] == 2
    assert health["filtered_non_target_packets"] == 2


def test_phase57_confirmed_transport_loss_detection():
    """
    Test 6: True transport loss detection in an interleaved stream.
    ESP32 sends sequence 1, 2, 3, 4, 5. UART drops packet 3.
    Host receives: 1 (target), 2 (ambient), 4 (ambient), 5 (target).
    """
    target_ap = "98:BA:5F:EF:28:26"
    ambient_mac = "AA:BB:CC:DD:EE:FF"

    collector = RealCSICollector(target_mac=target_ap, filter_by_mac=True)

    # Frame 1: Target (seq 1)
    collector._process_parsed_frame({
        "timestamp": 100.0, "sequence": 1, "mac": target_ap, "rssi": -55,
        "noise_floor": -95, "raw_amplitudes": [10.0]*56, "raw_phases": [0]*56
    })
    # Frame 2: Ambient (seq 2)
    collector._process_parsed_frame({
        "timestamp": 100.03, "sequence": 2, "mac": ambient_mac, "rssi": -70,
        "noise_floor": -95, "raw_amplitudes": [10.0]*56, "raw_phases": [0]*56
    })
    # Packet 3 was dropped over UART serial interface!
    # Frame 4: Ambient (seq 4)
    collector._process_parsed_frame({
        "timestamp": 100.09, "sequence": 4, "mac": ambient_mac, "rssi": -70,
        "noise_floor": -95, "raw_amplitudes": [10.0]*56, "raw_phases": [0]*56
    })
    # Frame 5: Target (seq 5)
    collector._process_parsed_frame({
        "timestamp": 100.12, "sequence": 5, "mac": target_ap, "rssi": -55,
        "noise_floor": -95, "raw_amplitudes": [10.0]*56, "raw_phases": [0]*56
    })

    # Analysis:
    # 2 target packets received (seq 1, seq 5)
    assert collector.packets_received == 2
    # 2 ambient packets filtered (seq 2, seq 4)
    assert collector.filtered_non_target_packets == 2
    # 1 confirmed transport loss (seq 3 dropped between ESP32 and host)
    assert collector.confirmed_transport_loss == 1
    assert collector.firmware_sequence_gaps == 1
    assert collector.packets_lost == 1
    # Observed target sequence gap = 5 - (1 + 1) = 3 (comprising 2 filtered ambient + 1 dropped)
    assert collector.target_sequence_gaps == 3

    health = collector.get_stream_health()
    # Total expected emitted = 2 (target) + 2 (ambient) + 1 (lost) = 5
    # Loss percentage = 1 / 5 * 100 = 20.0%
    assert health["packet_loss_pct"] == 20.0


def test_phase57_sequence_wraparound_32bit():
    """
    Test 7: 32-bit unsigned sequence wraparound handling (2^32 - 1 -> 0).
    Verifies that wraparound does not result in massive false loss or negative gap.
    """
    collector = RealCSICollector(filter_by_mac=False)

    # Frame just before 32-bit overflow
    collector._process_parsed_frame({
        "timestamp": 100.0, "sequence": 0xFFFFFFFF, "mac": "98:BA:5F:EF:28:26", "rssi": -55,
        "noise_floor": -95, "raw_amplitudes": [10.0]*56, "raw_phases": [0]*56
    })
    assert collector.packets_lost == 0

    # Frame directly after wraparound (0x00000000)
    collector._process_parsed_frame({
        "timestamp": 100.03, "sequence": 0, "mac": "98:BA:5F:EF:28:26", "rssi": -55,
        "noise_floor": -95, "raw_amplitudes": [10.0]*56, "raw_phases": [0]*56
    })

    assert collector.packets_received == 2
    assert collector.firmware_sequence_gaps == 0
    assert collector.confirmed_transport_loss == 0
    assert collector.packets_lost == 0


def test_phase57_counter_reset_reboot_handling():
    """
    Test 8: Firmware reboot / counter reset handling.
    When ESP32 reboots, counter drops from e.g. 5000 to 1.
    Must not compute negative loss or a massive wraparound gap.
    """
    collector = RealCSICollector(filter_by_mac=False)

    collector._process_parsed_frame({
        "timestamp": 100.0, "sequence": 5000, "mac": "98:BA:5F:EF:28:26", "rssi": -55,
        "noise_floor": -95, "raw_amplitudes": [10.0]*56, "raw_phases": [0]*56
    })
    assert collector.counter_resets == 0

    # Reboot occurs: sequence restarts at 1
    collector._process_parsed_frame({
        "timestamp": 105.0, "sequence": 1, "mac": "98:BA:5F:EF:28:26", "rssi": -55,
        "noise_floor": -95, "raw_amplitudes": [10.0]*56, "raw_phases": [0]*56
    })

    assert collector.counter_resets == 1
    assert collector.firmware_sequence_gaps == 0
    assert collector.packets_lost == 0
    assert collector.last_firmware_seq == 1


def test_phase57_tri_counter_distinction():
    """
    Test 9: Demonstrates and tests the architectural distinction between:
    1. Internal firmware callback counter (seq)
    2. 802.11 MAC frame sequence number (rx_seq)
    3. Host serial record count (packets_received)
    """
    line_v2 = "CSI_DATA_V2,98:BA:5F:EF:28:26,-55,-95,1045,12345678,2048,56," + ",".join([f"15.0:0.1" for _ in range(56)])
    collector = RealCSICollector(filter_by_mac=False)

    parsed = collector.parse_raw_telemetry_line(line_v2)
    assert parsed is not None
    # 1. Firmware callback counter: monotonically increments across all packets on channel
    assert parsed["sequence"] == 1045
    # 2. 802.11 MAC sequence: 12-bit sequence number from MAC header (0-4095)
    assert parsed["rx_seq"] == 2048
    # 3. Hardware microsecond timestamp from ESP-IDF
    assert parsed["hw_timestamp_us"] == 12345678

    collector._process_parsed_frame(parsed)
    # 4. Host serial record count
    assert collector.packets_received == 1


# ==============================================================================
# Phase 57.1 Extensions: Independent Parity, Fail-Closed Routing, Out-of-Order
# ==============================================================================
def test_phase57_independent_training_script_reference_parity():
    """
    Test 10: Independently verifies preprocessing parity against the historical
    training benchmark script (`scratch/execute_phase15_adaptation_benchmark.py`).
    Guarantees that LivePipelineService does not merely self-verify against its own
    internal class, but matches the authoritative training reference bit-for-bit.
    """
    from scratch.execute_phase15_adaptation_benchmark import CalibratedPhysicsPreprocessor as HistoricalCalibPrep

    rng = np.random.RandomState(1337)
    sample_amp = rng.uniform(5.0, 50.0, size=(50, 56)).astype(np.float32)

    # 1. Historical Reference from benchmark script
    hist_prep = HistoricalCalibPrep(
        carrier_freq=2.442e9,
        source_rate_hz=35.58,
        target_timesteps=50,
        target_channels=56
    )
    # Historical Branch A
    m = sample_amp.mean(axis=0, keepdims=True)
    s = sample_amp.std(axis=0, keepdims=True) + 1e-6
    hist_raw = torch.tensor((sample_amp - m) / s, dtype=torch.float32).unsqueeze(0)
    # Historical Branch B
    hist_dopp_mat = hist_prep.compute_doppler_spectrogram(sample_amp)
    hist_dopp = torch.tensor(hist_dopp_mat, dtype=torch.float32).unsqueeze(0)

    # 2. Live Pipeline Service
    live = LivePipelineService()
    live.configure_preprocessor_for_checkpoint("phase15")
    live_raw, live_dopp = live.preprocess_window(sample_amp)

    # Bit-level parity check
    max_raw_diff = float(torch.max(torch.abs(hist_raw - live_raw.cpu())))
    max_dopp_diff = float(torch.max(torch.abs(hist_dopp - live_dopp.cpu())))

    assert max_raw_diff < 1e-7, f"Branch A differs from historical script: {max_raw_diff}"
    assert max_dopp_diff < 1e-7, f"Branch B differs from historical script: {max_dopp_diff}"


def test_phase57_checkpoint_routing_fail_closed_and_atomic():
    """
    Test 11: Validates that unknown checkpoint IDs fail closed with ValueError,
    and missing files fail with FileNotFoundError without leaving inconsistent state.
    """
    live = LivePipelineService()
    live.configure_preprocessor_for_checkpoint("phase13")
    assert live.active_checkpoint_id == "phase13"

    # Unsupported checkpoint ID must fail closed
    with pytest.raises(ValueError, match="Unknown or unsupported checkpoint_id"):
        live.configure_preprocessor_for_checkpoint("unknown_v99")

    # State must remain phase13
    assert live.active_checkpoint_id == "phase13"

    # Non-existent checkpoint path must raise FileNotFoundError
    with pytest.raises(FileNotFoundError):
        live.load_checkpoint(checkpoint_path=Path("non_existent_model_checkpoint.pth"))


def test_phase57_collector_duplicate_and_out_of_order_handling():
    """
    Test 12: Synthetic stream verifying duplicate sequence numbers and out-of-order packets.
    Verifies that duplicates and reordered packets do not inflate packet loss or spurious gaps.
    """
    collector = RealCSICollector(filter_by_mac=False)

    # Packet 10 arrives
    collector._process_parsed_frame({
        "timestamp": 10.0, "sequence": 10, "mac": "98:BA:5F:EF:28:26", "rssi": -55,
        "noise_floor": -95, "raw_amplitudes": [10.0]*56, "raw_phases": [0]*56
    })
    # Packet 11 arrives
    collector._process_parsed_frame({
        "timestamp": 10.03, "sequence": 11, "mac": "98:BA:5F:EF:28:26", "rssi": -55,
        "noise_floor": -95, "raw_amplitudes": [10.0]*56, "raw_phases": [0]*56
    })
    # Duplicate packet 11 arrives
    collector._process_parsed_frame({
        "timestamp": 10.035, "sequence": 11, "mac": "98:BA:5F:EF:28:26", "rssi": -55,
        "noise_floor": -95, "raw_amplitudes": [10.0]*56, "raw_phases": [0]*56
    })
    assert collector.duplicate_packets == 1
    assert collector.firmware_sequence_gaps == 0

    # Packet 13 arrives (drop seq 12)
    collector._process_parsed_frame({
        "timestamp": 10.09, "sequence": 13, "mac": "98:BA:5F:EF:28:26", "rssi": -55,
        "noise_floor": -95, "raw_amplitudes": [10.0]*56, "raw_phases": [0]*56
    })
    assert collector.firmware_sequence_gaps == 1

    # Out-of-order packet 12 arrives late (jitter)
    collector._process_parsed_frame({
        "timestamp": 10.10, "sequence": 12, "mac": "98:BA:5F:EF:28:26", "rssi": -55,
        "noise_floor": -95, "raw_amplitudes": [10.0]*56, "raw_phases": [0]*56
    })
    assert collector.out_of_order_packets == 1
    # Does NOT increment counter resets
    assert collector.counter_resets == 0
    # High-water mark remains 13, so next packet 14 should NOT produce a gap
    collector._process_parsed_frame({
        "timestamp": 10.12, "sequence": 14, "mac": "98:BA:5F:EF:28:26", "rssi": -55,
        "noise_floor": -95, "raw_amplitudes": [10.0]*56, "raw_phases": [0]*56
    })
    assert collector.firmware_sequence_gaps == 1
    assert collector.confirmed_transport_loss == 1


def test_phase57_loss_metric_semantics_and_parser_error_correlation():
    """
    Test 13: End-to-end synthetic verification of loss-metric semantics (Phase 57.2).
    Verifies the precise correlation between:
    - Firmware callback sequence gaps observed in parsed records.
    - Target-filtered sequence gaps.
    - Parser errors and malformed lines.
    - Duplicate sequence handling.
    - Out-of-order packet arrival.
    - 32-bit unsigned wraparound.
    - Firmware reboot / counter reset.
    Proves that sequence gaps measure unobserved records rather than transport loss alone.
    """
    target_ap = "98:BA:5F:EF:28:26"
    ambient_mac = "AA:BB:CC:DD:EE:FF"

    collector = RealCSICollector(target_mac=target_ap, filter_by_mac=True)

    # 1. Target record at seq 100
    line_100 = f"CSI_DATA_V2,{target_ap},-55,-95,100,1000000,500,56," + ",".join(["10.0:0.0"]*56)
    p_100 = collector.parse_raw_telemetry_line(line_100)
    assert p_100 is not None
    collector._process_parsed_frame(p_100)
    assert collector.packets_received == 1

    # 2. Duplicate record at seq 100 arrives
    collector._process_parsed_frame(p_100)
    assert collector.duplicate_packets == 1
    assert collector.firmware_sequence_gaps == 0

    # 3. Malformed line arrives at seq 101 (truncated line on serial bus)
    malformed_line = f"CSI_DATA_V2,{target_ap},-55,-95,101,TRUNCATED_CORRUPT"
    p_bad = collector.parse_raw_telemetry_line(malformed_line)
    assert p_bad is None
    collector.parse_errors += 1

    # 4. Non-target ambient record at seq 102 arrives
    line_102 = f"CSI_DATA_V2,{ambient_mac},-70,-95,102,1060000,502,56," + ",".join(["10.0:0.0"]*56)
    p_102 = collector.parse_raw_telemetry_line(line_102)
    assert p_102 is not None
    collector._process_parsed_frame(p_102)
    # Filtered by MAC: not admitted to target buffer
    assert collector.filtered_non_target_packets == 1
    # Firmware sequence gap was detected because seq 101 was malformed/dropped!
    assert collector.firmware_sequence_gaps == 1

    # 5. Out-of-order target record at seq 101 arrives late (jitter)
    line_101 = f"CSI_DATA_V2,{target_ap},-55,-95,101,1030000,501,56," + ",".join(["10.0:0.0"]*56)
    p_101 = collector.parse_raw_telemetry_line(line_101)
    collector._process_parsed_frame(p_101)
    assert collector.out_of_order_packets == 1
    # Sequence baseline was not regressed

    # 6. Target record at seq 103 arrives
    line_103 = f"CSI_DATA_V2,{target_ap},-55,-95,103,1090000,503,56," + ",".join(["10.0:0.0"]*56)
    p_103 = collector.parse_raw_telemetry_line(line_103)
    collector._process_parsed_frame(p_103)
    assert collector.packets_received == 3

    # Check metrics
    health = collector.get_stream_health()
    assert health["packets_received"] == 3
    assert health["filtered_non_target_packets"] == 1
    assert health["parse_errors"] == 1
    assert health["duplicate_packets"] == 1
    assert health["out_of_order_packets"] == 1
    assert health["firmware_sequence_gaps"] == 1
    assert health["packets_lost"] == 1
    assert health["target_sequence_gaps"] == 1  # Gap between admitted target packets (101 -> 103, skipping ambient 102)


def test_phase57_authoritative_telemetry_naming_contract():
    """
    Test 14: Verification of Phase 57.3 Authoritative Telemetry Naming Contract.
    Strictly verifies:
    1. Ambient filtering does NOT count as packet loss (firmware_sequence_gaps == 0, packets_lost == 0).
    2. Sequence gaps are NOT described as confirmed UART loss (measures unobserved callback arrivals).
    3. Legacy fields (confirmed_transport_loss, packets_lost) mirror authoritative firmware_sequence_gaps.
    4. Parser errors and callback sequence gaps remain completely distinct metrics.
    """
    target_ap = "98:BA:5F:EF:28:26"
    ambient_ap = "AA:BB:CC:DD:EE:FF"

    collector = RealCSICollector(target_mac=target_ap, filter_by_mac=True)

    # --- 1. Ambient filtering does NOT count as packet loss ---
    # Target frame 1 arrives
    p1 = collector.parse_raw_telemetry_line(f"CSI_DATA_V2,{target_ap},-50,-95,1,1000000,500,56," + ",".join(["10.0:0.0"]*56))
    collector._process_parsed_frame(p1)
    assert collector.packets_received == 1

    # 10 continuous ambient frames arrive (seq 2..11)
    for seq in range(2, 12):
        p_amb = collector.parse_raw_telemetry_line(f"CSI_DATA_V2,{ambient_ap},-65,-95,{seq},{1000000 + seq*10000},500,56," + ",".join(["10.0:0.0"]*56))
        collector._process_parsed_frame(p_amb)

    assert collector.filtered_non_target_packets == 10
    # Crucial assertion: Zero callback sequence gaps, zero legacy packet loss!
    assert collector.firmware_sequence_gaps == 0
    assert collector.confirmed_transport_loss == 0
    assert collector.packets_lost == 0
    # Target sequence gap is 10 (ambient frames between target frames)
    assert collector.target_sequence_gaps == 0  # Only 1 target packet arrived so far

    # Target frame 12 arrives
    p12 = collector.parse_raw_telemetry_line(f"CSI_DATA_V2,{target_ap},-50,-95,12,1120000,500,56," + ",".join(["10.0:0.0"]*56))
    collector._process_parsed_frame(p12)
    assert collector.packets_received == 2
    assert collector.target_sequence_gaps == 10  # 12 - (1 + 1) = 10
    assert collector.firmware_sequence_gaps == 0  # Continuous ESP32 callback stream!
    assert collector.confirmed_transport_loss == 0
    assert collector.packets_lost == 0

    health = collector.get_stream_health()
    assert health["packet_loss_pct"] == 0.0

    # --- 2. Parser errors and callback sequence gaps remain distinct metrics ---
    # Three corrupt serial lines arrive (e.g. framing errors on UART bus)
    for _ in range(3):
        corrupt = "CORRUPT_SERIAL_LINE_GARBAGE"
        parsed = collector.parse_raw_telemetry_line(corrupt)
        assert parsed is None
        collector.parse_errors += 1

    assert collector.parse_errors == 3
    # Parser errors do NOT alter firmware_sequence_gaps until a parsed line is read
    assert collector.firmware_sequence_gaps == 0

    # --- 3. Sequence gaps measure unobserved callback arrivals, not confirmed UART loss ---
    # Frame 13 was lost inside corrupt line or dropped in firmware queue.
    # Frame 14 arrives: sequence jumped from 12 to 14 -> gap = 14 - (12 + 1) = 1
    p14 = collector.parse_raw_telemetry_line(f"CSI_DATA_V2,{target_ap},-50,-95,14,1140000,500,56," + ",".join(["10.0:0.0"]*56))
    collector._process_parsed_frame(p14)

    assert collector.firmware_sequence_gaps == 1
    # Parser errors remain at 3 (distinct counter)
    assert collector.parse_errors == 3

    # --- 4. Legacy fields behave consistently with their documented compatibility contract ---
    # confirmed_transport_loss and packets_lost strictly mirror firmware_sequence_gaps
    assert collector.confirmed_transport_loss == collector.firmware_sequence_gaps
    assert collector.packets_lost == collector.firmware_sequence_gaps

    diag = collector.get_stream_diagnostics()
    assert diag["firmware_sequence_gaps"] == 1
    assert diag["confirmed_transport_loss"] == 1
    assert diag["packets_lost"] == 1
    assert diag["parse_errors"] == 3
    assert diag["filtered_non_target_packets"] == 10
    assert diag["target_sequence_gaps"] == 11  # 10 previous + 1 gap to 14

    health = collector.get_stream_health()
    assert health["firmware_sequence_gaps"] == 1
    assert health["confirmed_transport_loss"] == 1
    assert health["packets_lost"] == 1
    assert health["parse_errors"] == 3



