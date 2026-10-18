"""
CSIFormer Phase 17 — Execute and Validate Participant-Independent Split Generation.
Tests both 3-way split rejection (insufficient participants error) and 2-way LOSO partitioning.
"""

import sys
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))
sys.path.append(str(BASE_DIR / "backend"))

from app.services.split_generator import (
    ParticipantIndependentSplitGenerator,
    InsufficientParticipantsError
)

def run():
    manifest_path = BASE_DIR / "data" / "real_csi_dataset" / "dataset_manifest.json"
    print("=" * 80)
    print("PHASE 17 — PARTICIPANT-INDEPENDENT SPLIT GENERATOR VALIDATION")
    print("=" * 80)

    generator = ParticipantIndependentSplitGenerator(manifest_path)
    summary = generator.get_participant_summary()
    print("Participant Breakdown:")
    for p, stats in summary.items():
        print(f"  {p}: {stats['session_count']} sessions, {stats['total_packets']} packets, {stats['total_windows']} windows")
        print(f"    Activities: {stats['activity_windows']}")

    # 1. Test 3-way split rejection
    print("\n[Test 1] Attempting 3-way participant-independent split (Train / Val / Test)...")
    try:
        generator.generate_loso_split(test_participant="Participant_02", val_participant="Participant_01")
        print("  ERROR: Expected InsufficientParticipantsError was NOT raised!")
    except InsufficientParticipantsError as e:
        print(f"  SUCCESS: Correctly caught InsufficientParticipantsError:\n    \"{e}\"")

    # 2. Test 2-way LOSO split (Train: Participant_01, Test: Participant_02)
    print("\n[Test 2] Generating 2-way Leave-One-Subject-Out split (Train: Participant_01, Test: Participant_02)...")
    out_manifest = BASE_DIR / "data" / "real_csi_dataset" / "dataset_manifest_p17_loso.json"
    loso_result = generator.generate_loso_split(
        test_participant="Participant_02",
        val_participant=None,
        output_manifest_path=out_manifest
    )

    print(f"  Manifest written to: {out_manifest.name}")
    print(f"  Splits Summary: {loso_result['splits_summary']}")
    print(f"  Class Coverage:")
    print(f"    Train Classes:   {loso_result['class_coverage']['train_classes']}")
    print(f"    Test Classes:    {loso_result['class_coverage']['test_classes']}")
    print(f"    Missing in Test: {loso_result['class_coverage']['missing_in_test']}")

    # Output metrics JSON for report
    metrics_path = BASE_DIR / "reports" / "phase17_split_metrics.json"
    metrics_data = {
        "participants": generator.participants,
        "participant_summary": summary,
        "splits_summary": loso_result["splits_summary"],
        "class_coverage": loso_result["class_coverage"],
        "three_way_split_feasible": False,
        "three_way_error_reason": "Only 2 participants present in dataset; minimum 3 required for zero-leakage Train/Val/Test."
    }
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(metrics_data, f, indent=2)
    print(f"  Metrics dumped to: {metrics_path.name}")
    print("=" * 80)

if __name__ == "__main__":
    run()
