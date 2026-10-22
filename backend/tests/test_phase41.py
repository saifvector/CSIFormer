"""
CSIFormer Phase 41 — Multi-Room Dataset Collection Campaign Design Test Suite.

Verifies:
1. Protected checkpoint and manifest hash invariance.
2. Historical dataset evidence audit (74 sessions, 23 p15 with raw=None, 51 phase16 with raw=5, 64 Lab, 10 Office).
3. Campaign quantitative targets and window accounting math (500 sessions, 2,500 windows, 8.0s duration).
4. Collection quality gates and rejection criteria (sampling rate, packet loss, monotonicity, constant channels).
5. Pre-collection split rules and partition isolation (zero participant and zero room leakage to test).
6. Hardware feasibility contract (SISO 1T1R enforcement, rejection of unsubstantiated MIMO claims).
"""

import json
import hashlib
import sys
from pathlib import Path
from typing import Dict, Any, List, Set, Optional, Tuple
import pytest
import numpy as np

BASE_DIR = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = BASE_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

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


def test_phase41_protected_file_invariance():
    """Verify production and experimental checkpoints and current dataset manifest remain unchanged."""
    p13_path = MODELS_DIR / "csiformer_phase13_best.pth"
    p15_path = MODELS_DIR / "csiformer_phase15_adapted.pth"

    assert p13_path.exists(), f"Missing production checkpoint: {p13_path}"
    assert p15_path.exists(), f"Missing experimental checkpoint: {p15_path}"
    assert MANIFEST_PATH.exists(), f"Missing dataset manifest: {MANIFEST_PATH}"

    assert compute_md5(p13_path) == EXPECTED_PHASE13_MD5, "Phase 13 checkpoint modified!"
    assert compute_md5(p15_path) == EXPECTED_PHASE15_MD5, "Phase 15 checkpoint modified!"
    assert compute_md5(MANIFEST_PATH) == EXPECTED_MANIFEST_MD5, "Manifest file modified!"


def test_phase41_historical_evidence_audit():
    """Verify exact historical physical counts, raw subcarrier decimation, and room/participant coverage."""
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    sessions = manifest["sessions"]
    assert len(sessions) == 74, f"Expected 74 sessions, found {len(sessions)}"

    raw_none_count = 0
    raw_5_count = 0
    rooms = set()
    participants = set()
    activities = set()

    for s in sessions:
        sid = s["session_id"]
        jfile = s.get("json_file", f"{sid}.json")
        jpath = DATASET_DIR / jfile
        assert jpath.exists(), f"Missing session file: {jpath}"

        with open(jpath, "r", encoding="utf-8") as f:
            data = json.load(f)
        meta = data.get("metadata", {})
        frames = data.get("frames", [])

        rooms.add(meta.get("room_type"))
        participants.add(meta.get("participant_id"))
        activities.add(meta.get("ground_truth_activity") or s.get("activity_label"))

        first_frame = frames[0] if frames else {}
        if "raw_amplitudes" in first_frame:
            assert len(first_frame["raw_amplitudes"]) == 5, f"Expected 5 raw subcarriers in {sid}"
            raw_5_count += 1
        else:
            raw_none_count += 1

    assert raw_none_count == 23, f"Expected 23 p15 sessions with raw=None, found {raw_none_count}"
    assert raw_5_count == 51, f"Expected 51 phase16 sessions with raw=5, found {raw_5_count}"
    assert rooms == {"Laboratory", "Office"}, f"Expected only Laboratory and Office, found {rooms}"
    assert participants == {f"Participant_0{i}" for i in range(1, 6)}, f"Unexpected participants: {participants}"
    assert activities == {"push_pull", "clap", "walk", "static", "sit", "fall"}


def test_phase41_campaign_quantitative_targets_and_window_math():
    """Verify quantitative target relationships: duration, frame rate, retained windows, remainder frames."""
    # Campaign parameters
    target_sessions_per_class = 100
    target_classes = ["push_pull", "clap", "walk", "static", "sit"]
    num_classes = len(target_classes)
    total_sessions = target_sessions_per_class * num_classes
    assert total_sessions == 500

    target_duration_s = 8.0
    nominal_rate_hz = 35.0
    expected_frames_per_session = int(target_duration_s * nominal_rate_hz)  # 280 frames
    window_size = 50

    retained_windows_per_session = expected_frames_per_session // window_size  # 5 windows
    dropped_frames_per_session = expected_frames_per_session % window_size   # 30 frames

    assert retained_windows_per_session == 5
    assert dropped_frames_per_session == 30
    assert dropped_frames_per_session / expected_frames_per_session < 0.12  # Remainder loss < 12% (vs 25.5% in Phase 16)

    total_windows_per_class = target_sessions_per_class * retained_windows_per_session
    assert total_windows_per_class == 500  # 500 retained non-overlapping windows per class
    assert total_sessions * retained_windows_per_session == 2500  # Total windows across dataset

    # Participant burden calculation
    num_participants = 10
    sessions_per_participant = total_sessions // num_participants  # 50 sessions each
    assert sessions_per_participant == 50

    active_recording_time_s = sessions_per_participant * target_duration_s  # 400s = 6.67 minutes
    inter_trial_rest_s = 12.0
    total_session_time_min = (sessions_per_participant * (target_duration_s + inter_trial_rest_s)) / 60.0
    assert total_session_time_min < 20.0  # Under 20 minutes active recording time per participant


def test_phase41_quality_gates_logic():
    """Verify automated quality gate criteria for session validation and rejection."""
    def validate_session_telemetry(
        duration_s: float,
        frames: int,
        empirical_rate_hz: float,
        loss_rate: float,
        is_monotonic: bool,
        amplitudes: np.ndarray,
        rssi: float,
        noise: float
    ) -> Tuple[bool, Optional[str]]:
        if duration_s < 7.5 or frames < 250:
            return False, "insufficient_duration_or_frames"
        if not (32.0 <= empirical_rate_hz <= 42.0):
            return False, f"sampling_rate_out_of_bounds_{empirical_rate_hz}"
        if loss_rate > 0.02:
            return False, f"packet_loss_exceeds_threshold_{loss_rate}"
        if not is_monotonic:
            return False, "non_monotonic_timestamps"
        if np.any(np.isnan(amplitudes)) or np.any(np.isinf(amplitudes)):
            return False, "non_finite_amplitudes"
        if np.max(np.std(amplitudes, axis=0)) < 1e-4:
            return False, "flatline_constant_channel"
        if (rssi - noise) < 15.0:
            return False, "insufficient_snr"
        return True, None

    # Valid session trial
    valid_amps = np.random.normal(loc=20.0, scale=3.0, size=(280, 56))
    passed, reason = validate_session_telemetry(
        duration_s=8.02, frames=281, empirical_rate_hz=35.1, loss_rate=0.005,
        is_monotonic=True, amplitudes=valid_amps, rssi=-58.0, noise=-95.0
    )
    assert passed is True
    assert reason is None

    # Rejection: Excessive packet loss
    passed, reason = validate_session_telemetry(
        duration_s=8.02, frames=281, empirical_rate_hz=35.1, loss_rate=0.05,
        is_monotonic=True, amplitudes=valid_amps, rssi=-58.0, noise=-95.0
    )
    assert passed is False
    assert "packet_loss" in reason

    # Rejection: Constant flatline channel
    flat_amps = np.ones((280, 56)) * 20.0
    passed, reason = validate_session_telemetry(
        duration_s=8.02, frames=281, empirical_rate_hz=35.1, loss_rate=0.0,
        is_monotonic=True, amplitudes=flat_amps, rssi=-58.0, noise=-95.0
    )
    assert passed is False
    assert "flatline" in reason

    # Rejection: Insufficient SNR
    passed, reason = validate_session_telemetry(
        duration_s=8.02, frames=281, empirical_rate_hz=35.1, loss_rate=0.0,
        is_monotonic=True, amplitudes=valid_amps, rssi=-85.0, noise=-95.0  # SNR = 10 dB < 15 dB
    )
    assert passed is False
    assert "snr" in reason


def test_phase41_pre_collection_split_architecture():
    """Verify participant and room isolation rules on the planned 10-subject, 3-room campaign matrix."""
    participants = [f"Participant_{i:02d}" for i in range(1, 11)]
    target_classes = ["push_pull", "clap", "walk", "static", "sit"]

    # Pre-allocation rule:
    # 10 participants, 50 sessions each = 500 sessions total.
    # Train (6 subjects): P01-P06 in Room1 (25 sess) and Room2 (25 sess) -> 300 sessions (1,500 windows, 60.0%)
    # Val (2 subjects): P07-P08 in Room1 (25 sess) and Room2 (25 sess) -> 100 sessions (500 windows, 20.0%)
    # Test (2 subjects): P09-P10 in Room3 (50 sess) -> 100 sessions (500 windows, 20.0%)
    train_subjects = set(participants[0:6])
    val_subjects = set(participants[6:8])
    test_subjects = set(participants[8:10])

    train_rooms = {"Laboratory_Room1", "Office_Room2"}
    val_rooms = {"Laboratory_Room1", "Office_Room2"}
    test_rooms = {"Conference_Room3"}

    # Invariant 1: Zero participant overlap
    assert len(train_subjects & val_subjects) == 0
    assert len(train_subjects & test_subjects) == 0
    assert len(val_subjects & test_subjects) == 0

    # Invariant 2: Test room isolation (Strict Room-Held-Out)
    assert test_rooms.isdisjoint(train_rooms)
    assert test_rooms.isdisjoint(val_rooms)

    # Invariant 3: Class representation across partitions
    sessions = []
    sid_counter = 0

    for p in participants:
        if p in test_subjects:
            # 50 sessions in Room3 (10 per class, 2 distances)
            for c in target_classes:
                for rep in range(10):
                    sid_counter += 1
                    dist = "2.0m" if rep < 5 else "3.5m"
                    sessions.append({
                        "session_id": f"sim_session_{sid_counter:04d}",
                        "participant_id": p,
                        "room": "Conference_Room3",
                        "activity": c,
                        "distance": dist,
                        "split": "test",
                        "windows": 5
                    })
        else:
            # 25 sessions in Room1 (5 per class), 25 sessions in Room2 (5 per class)
            split = "val" if p in val_subjects else "train"
            for r in ["Laboratory_Room1", "Office_Room2"]:
                for c in target_classes:
                    for rep in range(5):
                        sid_counter += 1
                        sessions.append({
                            "session_id": f"sim_session_{sid_counter:04d}",
                            "participant_id": p,
                            "room": r,
                            "activity": c,
                            "distance": "2.5m",
                            "split": split,
                            "windows": 5
                        })

    assert len(sessions) == 500, f"Expected 500 sessions, found {len(sessions)}"

    # Verify partition summaries
    train_wins = sum(s["windows"] for s in sessions if s["split"] == "train")
    val_wins = sum(s["windows"] for s in sessions if s["split"] == "val")
    test_wins = sum(s["windows"] for s in sessions if s["split"] == "test")
    total_wins = train_wins + val_wins + test_wins

    assert train_wins == 1500  # 300 sessions * 5
    assert val_wins == 500     # 100 sessions * 5
    assert test_wins == 500    # 100 sessions * 5
    assert total_wins == 2500

    # Exact ratio check: 60% train, 20% val, 20% test
    assert train_wins / total_wins == 0.60
    assert val_wins / total_wins == 0.20
    assert test_wins / total_wins == 0.20

    # Verify per-class coverage in every partition
    for split_name, expected_count in [("train", 300), ("val", 100), ("test", 100)]:
        for c in target_classes:
            wins_c = sum(s["windows"] for s in sessions if s["split"] == split_name and s["activity"] == c)
            assert wins_c == expected_count, f"Expected {expected_count} windows for {c} in {split_name}, found {wins_c}"


def test_phase41_hardware_siso_contract():
    """Verify hardware contract strictly enforces single RF stream (SISO 1T1R) and rejects invalid MIMO."""
    def verify_hardware_capabilities(board_name: str, requested_rx_antennas: int) -> bool:
        # ESP32-S3 has a single physical RF transceiver (1T1R)
        if "ESP32-S3" in board_name:
            if requested_rx_antennas > 1:
                return False  # Hardware does NOT support native multi-antenna diversity / MIMO
            return True
        return False

    # Valid ESP32-S3 SISO
    assert verify_hardware_capabilities("ESP32-S3-DevKitC-1", requested_rx_antennas=1) is True

    # Rejection of unsupported MIMO claims
    assert verify_hardware_capabilities("ESP32-S3-DevKitC-1", requested_rx_antennas=2) is False
    assert verify_hardware_capabilities("ESP32-S3-DevKitC-1", requested_rx_antennas=3) is False
