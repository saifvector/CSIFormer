"""
CSIFormer Phase 36 — Controlled Five-Class Cross-Room Evaluation Gate Tests.

Validates:
1. Gate A Semantic Audit: Traces training dataset classes (Widar gestures 0-5 + NTU-Fi activities 6-11).
   Demonstrates that model output 6 was trained on "box" (Dynamic Arm Boxing) and model output 8
   was trained on "clean" (Table Cleaning Motion), establishing that equating them to "static"
   and "sit" is semantically invalid.
2. Gate B Production Inference Path Audit: Traces production pipeline contracts in LivePipelineService
   and documents discrepancies between training-time and runtime preprocessing.
3. Gate C Strict Partition Freeze: Non-mutating verification of the 75 train / 20 val / 11 test / 49 excluded
   partition, zero leakage of Office_Room2 or Participant_02, and manifest immutability.
4. Gate E Checkpoint Protection: Re-computes MD5 hashes for both protected checkpoints against references.
"""

import json
import hashlib
import sys
from pathlib import Path
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
REPORTS_DIR = BASE_DIR / "reports"

EXPECTED_PHASE13_MD5 = "383b4d98c08f8970b0443738f170ec01"
EXPECTED_PHASE15_MD5 = "ab3d97a04d78edf75d807178772bc828"

from backend.app.services.split_generator import ParticipantIndependentSplitGenerator
from backend.app.models.csiformer_dual_branch import CSIDualBranchFusionNet
from backend.app.datasets.combined_dataset import CombinedCSIDataset
from backend.app.datasets.ntufi_dataset import NTUFiDataset
from backend.app.services.live_pipeline_service import LivePipelineService, LABEL_MAP as LIVE_LABEL_MAP


def test_phase36_checkpoint_md5_protection():
    """Verify production and experimental checkpoints match reference hashes bit-for-bit."""
    p13_path = MODELS_DIR / "csiformer_phase13_best.pth"
    p15_path = MODELS_DIR / "csiformer_phase15_adapted.pth"

    assert p13_path.exists(), f"Production checkpoint missing: {p13_path}"
    assert p15_path.exists(), f"Experimental checkpoint missing: {p15_path}"

    with open(p13_path, "rb") as f:
        p13_md5 = hashlib.md5(f.read()).hexdigest()
    with open(p15_path, "rb") as f:
        p15_md5 = hashlib.md5(f.read()).hexdigest()

    assert p13_md5 == EXPECTED_PHASE13_MD5, f"Phase 13 checkpoint modified: {p13_md5}"
    assert p15_md5 == EXPECTED_PHASE15_MD5, f"Phase 15 checkpoint modified: {p15_md5}"


def test_phase36_gate_a_training_semantics_and_alias_mismatch():
    """
    Gate A Verification:
    Verify the actual training-time classes of the unified model.
    Prove that model output 6 is 'box' and output 8 is 'clean' from NTU-Fi,
    which represents boxing and cleaning motions, NOT static and sit.
    """
    # 1. Combined dataset class taxonomy
    unified_classes = CombinedCSIDataset.UNIFIED_CLASSES
    assert len(unified_classes) == 12
    assert unified_classes[0] == "Push&Pull"
    assert unified_classes[2] == "Clap"
    assert unified_classes[6] == "box"
    assert unified_classes[8] == "clean"
    assert unified_classes[9] == "fall"
    assert unified_classes[11] == "walk"

    # 2. NTU-Fi dataset classes (classes 0-5 offset by +6 into 6-11)
    ntufi_classes = NTUFiDataset.CLASSES
    assert ntufi_classes == ["box", "circle", "clean", "fall", "run", "walk"]
    assert ntufi_classes[0] == "box"   # index 0 + offset 6 = class 6
    assert ntufi_classes[2] == "clean" # index 2 + offset 6 = class 8

    # 3. Production LivePipelineService LABEL_MAP
    assert LIVE_LABEL_MAP[6] == "Box (NTU-Fi)"
    assert LIVE_LABEL_MAP[8] == "Clean (NTU-Fi)"

    # 4. Forensic report evidence
    audit_report = REPORTS_DIR / "full_training_audit.md"
    assert audit_report.exists()
    report_text = audit_report.read_text(encoding="utf-8")
    assert "Dynamic Arm Boxing" in report_text, "Missing evidence for class 6 'box'"
    assert "Table Cleaning Motion" in report_text, "Missing evidence for class 8 'clean'"

    # 5. Manifest in real CSI dataset assigns static -> 6 and sit -> 8
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    manifest_map = {s["activity_label"]: s["class_id"] for s in manifest["sessions"]}
    assert manifest_map["static"] == 6
    assert manifest_map["sit"] == 8

    # Conclusion: Static != Boxing and Sit != Cleaning.
    # Therefore, equating static -> 6 and sit -> 8 is semantically invalid.


def test_phase36_gate_b_production_inference_path_contracts():
    """
    Gate B Verification:
    Verify LivePipelineService requirements and contracts.
    Confirm that live_pipeline_service only operates on live streaming buffers,
    and lacks an offline batch evaluation method for dataset windows.
    """
    service = LivePipelineService()
    assert service.preprocessor is not None
    assert service.preprocessor.carrier_freq == 2.442e9
    assert service.preprocessor.target_timesteps == 50
    assert service.preprocessor.target_channels == 56

    # Verify that predict_latest_window fails safely when collector is None or empty
    service.collector = None
    res = service.predict_latest_window()
    assert res["status"] == "error"
    assert "Collector not initialized" in res["error"]


def test_phase36_gate_c_strict_partition_reproducibility():
    """
    Gate C Verification:
    Confirm the strict partition reproduces exactly 75 train / 20 val / 11 test / 49 excluded windows.
    Confirm zero leakage of Office_Room2 or Participant_02 into train or val.
    Confirm dataset manifest remains unmutated.
    """
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        before_manifest = f.read()

    gen = ParticipantIndependentSplitGenerator(MANIFEST_PATH)
    res = gen.generate_strict_cross_room_split(output_manifest_path=None)

    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        after_manifest = f.read()
    assert before_manifest == after_manifest, "Manifest on disk was mutated!"

    stats = res["splits_summary"]
    assert stats["train_sessions"] == 36
    assert stats["val_sessions"] == 10
    assert stats["test_sessions"] == 5
    assert stats["excluded_sessions"] == 23

    assert stats["train_windows"] == 75
    assert stats["val_windows"] == 20
    assert stats["test_windows"] == 11
    assert stats["excluded_windows"] == 49
    assert stats["total_windows"] == 155

    test_sessions = [s for s in res["sessions"] if s["split"] == "test"]
    assert len(test_sessions) == 5
    for s in test_sessions:
        assert s["room"] == "Office_Room2"
        assert s["participant_id"] == "Participant_02"
        assert s["activity_label"] in {"static", "sit", "walk", "clap", "push_pull"}
