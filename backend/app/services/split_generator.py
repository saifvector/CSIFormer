"""
CSIFormer Phase 17 — Participant-Independent (LOSO) Split Generator.

Generates strictly participant-independent dataset partitions:
- Zero participant overlap between Train, Validation, and Test splits.
- Zero window overlap between splits.
- Full session grouping (all windows from a session stay in that session's split).
- Formal class balance and coverage reporting.
- Strict error raising if participant count is insufficient for requested split topology.
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Set, Optional, Tuple
import numpy as np


class InsufficientParticipantsError(ValueError):
    """Raised when the dataset has fewer participants than required for independent splits."""
    pass


class ParticipantIndependentSplitGenerator:
    """
    Generates and validates participant-independent (Leave-One-Subject-Out) dataset splits.
    """

    def __init__(self, manifest_path: Path):
        self.manifest_path = Path(manifest_path)
        if not self.manifest_path.exists():
            raise FileNotFoundError(f"Manifest not found: {self.manifest_path}")

        with open(self.manifest_path, "r", encoding="utf-8") as f:
            self.manifest = json.load(f)

        self.sessions = self.manifest.get("sessions", [])
        self.participants = sorted(list(set(s.get("participant_id", "Unknown") for s in self.sessions)))

    def get_participant_summary(self) -> Dict[str, Any]:
        """Returns session counts, packet counts, and activity distribution per participant."""
        summary = {}
        dataset_dir = self.manifest_path.parent
        for p in self.participants:
            p_sessions = [s for s in self.sessions if s.get("participant_id") == p]
            activities = {}
            total_pkts = 0
            total_wins = 0
            for s in p_sessions:
                act = s.get("activity_label", "unknown")
                pkts = s.get("packet_count", 0)
                total_pkts += pkts
                wins = pkts // 50
                total_wins += wins
                activities[act] = activities.get(act, 0) + wins

            summary[p] = {
                "session_count": len(p_sessions),
                "total_packets": total_pkts,
                "total_windows": total_wins,
                "activity_windows": activities
            }
        return summary

    def generate_loso_split(
        self,
        test_participant: str,
        val_participant: Optional[str] = None,
        output_manifest_path: Optional[Path] = None
    ) -> Dict[str, Any]:
        """
        Creates a participant-independent partition.

        Args:
            test_participant: Participant assigned exclusively to the held-out test split.
            val_participant: Optional participant assigned exclusively to validation.
            output_manifest_path: Destination path for versioned manifest.

        Raises:
            InsufficientParticipantsError: If participant count is insufficient.
            ValueError: If requested participant is not in dataset.
        """
        if test_participant not in self.participants:
            raise ValueError(f"Requested test participant '{test_participant}' not found in dataset: {self.participants}")

        # Check for 3-way split feasibility
        if val_participant is not None:
            if val_participant not in self.participants:
                raise ValueError(f"Requested val participant '{val_participant}' not found in dataset: {self.participants}")
            if val_participant == test_participant:
                raise ValueError("Validation participant cannot be identical to test participant for participant-independent evaluation.")
            
            # Need at least 3 participants for a 3-way split
            if len(self.participants) < 3:
                raise InsufficientParticipantsError(
                    f"Cannot create a 3-way participant-independent split (Train/Val/Test) with only "
                    f"{len(self.participants)} participants ({self.participants}). "
                    f"Requires at least 3 distinct participants. Use a 2-way (Train/Test) split or expand the dataset."
                )
            train_participants = [p for p in self.participants if p != test_participant and p != val_participant]
        else:
            # 2-way split: Train vs Test
            if len(self.participants) < 2:
                raise InsufficientParticipantsError(
                    f"Cannot create an independent split with only {len(self.participants)} participant. "
                    f"Requires at least 2 distinct participants."
                )
            train_participants = [p for p in self.participants if p != test_participant]

        # Partition sessions
        partitioned_sessions = []
        split_counts = {"train": 0, "val": 0, "test": 0}
        split_windows = {"train": {}, "val": {}, "test": {}}

        for s in self.sessions:
            p = s.get("participant_id")
            act = s.get("activity_label", "unknown")
            wins = s.get("packet_count", 0) // 50

            s_copy = dict(s)
            if p == test_participant:
                assigned_split = "test"
            elif val_participant is not None and p == val_participant:
                assigned_split = "val"
            else:
                assigned_split = "train"

            s_copy["split"] = assigned_split
            partitioned_sessions.append(s_copy)

            split_counts[assigned_split] += 1
            split_windows[assigned_split][act] = split_windows[assigned_split].get(act, 0) + wins

        # Evaluate class coverage
        test_classes = set(split_windows["test"].keys())
        train_classes = set(split_windows["train"].keys())
        missing_in_test = train_classes - test_classes

        # Assemble new versioned manifest
        new_manifest = dict(self.manifest)
        new_manifest["split_protocol"] = "Leave-One-Subject-Out (LOSO) Participant-Independent"
        new_manifest["test_participant"] = test_participant
        new_manifest["val_participant"] = val_participant
        new_manifest["train_participants"] = train_participants
        new_manifest["splits_summary"] = {
            "train_sessions": split_counts["train"],
            "val_sessions": split_counts["val"],
            "test_sessions": split_counts["test"],
            "train_windows": sum(split_windows["train"].values()),
            "val_windows": sum(split_windows["val"].values()),
            "test_windows": sum(split_windows["test"].values()),
            "total_sessions": len(partitioned_sessions),
            "total_windows": sum(split_windows["train"].values()) + sum(split_windows["val"].values()) + sum(split_windows["test"].values())
        }
        new_manifest["class_coverage"] = {
            "train_classes": sorted(list(train_classes)),
            "test_classes": sorted(list(test_classes)),
            "missing_in_test": sorted(list(missing_in_test))
        }
        new_manifest["sessions"] = partitioned_sessions

        if output_manifest_path:
            output_manifest_path = Path(output_manifest_path)
            with open(output_manifest_path, "w", encoding="utf-8") as f:
                json.dump(new_manifest, f, indent=2)

        return new_manifest
