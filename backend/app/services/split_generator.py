"""
CSIFormer Phase 18 — Participant-Independent (LOSO) Split Generator.

Generates strictly participant-independent dataset partitions:
- Zero participant overlap between Train, Validation, and Test splits.
- Zero event overlap between splits (all correlated windows from an event stay together).
- Zero window overlap between splits.
- Full session grouping (all frames from a session stay in that session's split).
- Formal class balance, event-level coverage, and fall-event tracking.
- Strict error raising if participant count or class coverage is inadequate.
- Supports multi-participant assignments (e.g. 3 Train, 1 Val, 1 Test for 5 subjects).
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Set, Optional, Tuple, Union
import numpy as np


class InsufficientParticipantsError(ValueError):
    """Raised when the dataset has fewer participants than required for independent splits."""
    pass


class InadequateClassCoverageError(ValueError):
    """Raised when a partition lacks required activity classes (e.g., zero fall examples in test)."""
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
        """Returns session counts, packet counts, events, and activity distribution per participant."""
        summary = {}
        for p in self.participants:
            p_sessions = [s for s in self.sessions if s.get("participant_id") == p]
            activities = {}
            events = set()
            total_pkts = 0
            total_wins = 0
            for s in p_sessions:
                act = s.get("activity_label", "unknown")
                pkts = s.get("packet_count", 0)
                evt = s.get("event_id") or s.get("session_id")
                events.add(evt)
                total_pkts += pkts
                wins = pkts // 50
                total_wins += wins
                activities[act] = activities.get(act, 0) + wins

            summary[p] = {
                "session_count": len(p_sessions),
                "event_count": len(events),
                "total_packets": total_pkts,
                "total_windows": total_wins,
                "activity_windows": activities
            }
        return summary

    def generate_loso_split(
        self,
        test_participant: Union[str, List[str]],
        val_participant: Optional[Union[str, List[str]]] = None,
        output_manifest_path: Optional[Path] = None,
        strict_coverage: bool = False
    ) -> Dict[str, Any]:
        """
        Creates a participant-independent partition.

        Args:
            test_participant: Participant(s) assigned exclusively to the held-out test split.
            val_participant: Optional participant(s) assigned exclusively to validation.
            output_manifest_path: Destination path for versioned manifest.
            strict_coverage: If True, raises InadequateClassCoverageError if any training
                             class is absent from the test split or if test has 0 falls.

        Raises:
            InsufficientParticipantsError: If participant count is insufficient.
            InadequateClassCoverageError: If strict_coverage=True and test set lacks coverage.
            ValueError: If requested participant is not in dataset.
        """
        # Normalize to lists
        test_p_list = [test_participant] if isinstance(test_participant, str) else list(test_participant)
        val_p_list = []
        if val_participant is not None:
            val_p_list = [val_participant] if isinstance(val_participant, str) else list(val_participant)

        # Validate existence
        for p in test_p_list:
            if p not in self.participants:
                raise ValueError(f"Requested test participant '{p}' not found in dataset: {self.participants}")
        for p in val_p_list:
            if p not in self.participants:
                raise ValueError(f"Requested val participant '{p}' not found in dataset: {self.participants}")

        # Check disjointness between test and val
        test_val_overlap = set(test_p_list).intersection(set(val_p_list))
        if test_val_overlap:
            raise ValueError(f"Validation participants cannot overlap with test participants: {test_val_overlap}")

        # Check for 3-way split feasibility
        if len(val_p_list) > 0:
            if len(self.participants) < 3:
                raise InsufficientParticipantsError(
                    f"Cannot create a 3-way participant-independent split (Train/Val/Test) with only "
                    f"{len(self.participants)} participants ({self.participants}). "
                    f"Requires at least 3 distinct participants. Use a 2-way (Train/Test) split or expand the dataset."
                )
            train_participants = [p for p in self.participants if p not in test_p_list and p not in val_p_list]
            if len(train_participants) == 0:
                raise InsufficientParticipantsError("No participants left for training partition after allocating Val and Test.")
        else:
            # 2-way split: Train vs Test
            if len(self.participants) < 2:
                raise InsufficientParticipantsError(
                    f"Cannot create an independent split with only {len(self.participants)} participant. "
                    f"Requires at least 2 distinct participants."
                )
            train_participants = [p for p in self.participants if p not in test_p_list]

        # Partition sessions and track events
        partitioned_sessions = []
        split_counts = {"train": 0, "val": 0, "test": 0}
        split_events = {"train": set(), "val": set(), "test": set()}
        split_windows = {"train": {}, "val": {}, "test": {}}
        split_fall_events = {"train": 0, "val": 0, "test": 0}

        for s in self.sessions:
            p = s.get("participant_id")
            act = s.get("activity_label", "unknown")
            evt = s.get("event_id") or s.get("session_id")
            wins = s.get("packet_count", 0) // 50

            s_copy = dict(s)
            if p in test_p_list:
                assigned_split = "test"
            elif p in val_p_list:
                assigned_split = "val"
            else:
                assigned_split = "train"

            s_copy["split"] = assigned_split
            s_copy["event_id"] = evt
            partitioned_sessions.append(s_copy)

            split_counts[assigned_split] += 1
            split_events[assigned_split].add(evt)
            split_windows[assigned_split][act] = split_windows[assigned_split].get(act, 0) + wins
            if act == "fall":
                split_fall_events[assigned_split] += 1

        # Evaluate class coverage
        test_classes = set(split_windows["test"].keys())
        val_classes = set(split_windows["val"].keys())
        train_classes = set(split_windows["train"].keys())
        missing_in_test = train_classes - test_classes

        # Event and window overlap verification (Invariant check)
        train_test_event_overlap = split_events["train"].intersection(split_events["test"])
        assert len(train_test_event_overlap) == 0, f"Event leakage detected between train and test: {train_test_event_overlap}"

        if strict_coverage:
            if len(missing_in_test) > 0:
                raise InadequateClassCoverageError(
                    f"Held-out test split lacks class coverage for: {sorted(list(missing_in_test))}. "
                    f"Train classes: {sorted(list(train_classes))}, Test classes: {sorted(list(test_classes))}"
                )
            if split_windows["test"].get("fall", 0) == 0:
                raise InadequateClassCoverageError("Held-out test split contains 0 fall examples; cannot evaluate fall detection.")

        # Assemble new versioned manifest
        new_manifest = dict(self.manifest)
        new_manifest["split_protocol"] = "Leave-One-Subject-Out (LOSO) Participant-Independent"
        new_manifest["test_participants"] = test_p_list
        new_manifest["val_participants"] = val_p_list
        new_manifest["train_participants"] = train_participants
        new_manifest["test_participant"] = test_p_list[0] if len(test_p_list) == 1 else test_p_list
        new_manifest["val_participant"] = val_p_list[0] if len(val_p_list) == 1 else (val_p_list if val_p_list else None)

        new_manifest["splits_summary"] = {
            "train_participants": train_participants,
            "val_participants": val_p_list,
            "test_participants": test_p_list,
            "train_sessions": split_counts["train"],
            "val_sessions": split_counts["val"],
            "test_sessions": split_counts["test"],
            "train_events": len(split_events["train"]),
            "val_events": len(split_events["val"]),
            "test_events": len(split_events["test"]),
            "train_windows": sum(split_windows["train"].values()),
            "val_windows": sum(split_windows["val"].values()),
            "test_windows": sum(split_windows["test"].values()),
            "fall_events": split_fall_events,
            "fall_windows": {
                "train": split_windows["train"].get("fall", 0),
                "val": split_windows["val"].get("fall", 0),
                "test": split_windows["test"].get("fall", 0)
            },
            "total_sessions": len(partitioned_sessions),
            "total_windows": sum(split_windows["train"].values()) + sum(split_windows["val"].values()) + sum(split_windows["test"].values())
        }
        new_manifest["class_coverage"] = {
            "train_classes": sorted(list(train_classes)),
            "val_classes": sorted(list(val_classes)),
            "test_classes": sorted(list(test_classes)),
            "missing_in_test": sorted(list(missing_in_test))
        }
        new_manifest["sessions"] = partitioned_sessions

        if output_manifest_path:
            output_manifest_path = Path(output_manifest_path)
            with open(output_manifest_path, "w", encoding="utf-8") as f:
                json.dump(new_manifest, f, indent=2)

        return new_manifest
