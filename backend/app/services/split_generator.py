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

    def __init__(self, manifest_input: Union[Path, str, Dict[str, Any]]):
        if isinstance(manifest_input, dict):
            self.manifest_path = None
            self.manifest = manifest_input
        else:
            self.manifest_path = Path(manifest_input)
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
        train_val_event_overlap = split_events["train"].intersection(split_events["val"])
        val_test_event_overlap = split_events["val"].intersection(split_events["test"])
        assert len(train_test_event_overlap) == 0, f"Event leakage detected between train and test: {train_test_event_overlap}"
        assert len(train_val_event_overlap) == 0, f"Event leakage detected between train and val: {train_val_event_overlap}"
        assert len(val_test_event_overlap) == 0, f"Event leakage detected between val and test: {val_test_event_overlap}"

        # Participant overlap verification
        assert len(set(train_participants).intersection(set(test_p_list))) == 0, "Participant leakage between train and test"
        assert len(set(train_participants).intersection(set(val_p_list))) == 0, "Participant leakage between train and val"
        assert len(set(val_p_list).intersection(set(test_p_list))) == 0, "Participant leakage between val and test"

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

    def generate_strict_cross_room_split(
        self,
        test_room: str = "Office_Room2",
        test_participant: str = "Participant_02",
        val_participant: str = "Participant_05",
        train_participants: Optional[List[str]] = None,
        classes: Optional[List[str]] = None,
        output_manifest_path: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """
        Generates a strict room-held-out and participant-held-out evaluation partition (Phase 34).

        Invariants enforced:
        1. Training contains zero sessions from `test_room` (Office_Room2).
        2. Validation contains zero sessions from `test_room` (Office_Room2).
        3. Test contains ONLY sessions from `test_participant` in `test_room`.
        4. `test_participant` is completely absent from training and validation.
        5. Zero session, event, or overlapping window leakage between partitions.
        6. All requested target activity classes are represented in train, val, and test.
        7. Every eligible test window is assigned exactly once; excluded sessions are explicitly tracked.
        8. Fall detection is strictly excluded from this 5-class evaluation protocol.
        """
        if classes is None:
            target_classes = ["static", "sit", "walk", "clap", "push_pull"]
        else:
            target_classes = list(classes)

        if train_participants is None:
            train_p_list = [p for p in self.participants if p != test_participant and p != val_participant]
        else:
            train_p_list = list(train_participants)

        # Disjointness checks
        if test_participant in train_p_list:
            raise ValueError(f"Test participant '{test_participant}' cannot be in train participants: {train_p_list}")
        if test_participant == val_participant:
            raise ValueError(f"Test participant '{test_participant}' cannot be val participant.")
        if val_participant in train_p_list:
            raise ValueError(f"Val participant '{val_participant}' cannot be in train participants: {train_p_list}")

        partitioned_sessions = []
        split_counts = {"train": 0, "val": 0, "test": 0, "excluded": 0}
        split_events = {"train": set(), "val": set(), "test": set(), "excluded": set()}
        split_windows = {
            "train": {c: 0 for c in target_classes},
            "val": {c: 0 for c in target_classes},
            "test": {c: 0 for c in target_classes},
            "excluded": {}
        }
        exclusion_reasons = {}

        for s in self.sessions:
            s_copy = dict(s)
            p = s.get("participant_id")
            r = s.get("room")
            act = s.get("activity_label", "unknown")
            evt = s.get("event_id") or s.get("session_id")
            wins = s.get("packet_count", 0) // 50

            if act not in target_classes:
                assigned_split = "excluded"
                reason = f"non_target_activity_{act}"
            elif r == test_room:
                if p == test_participant:
                    assigned_split = "test"
                    reason = None
                else:
                    assigned_split = "excluded"
                    reason = f"other_participant_in_held_out_room_{p}"
            else:
                if p == test_participant:
                    assigned_split = "excluded"
                    reason = f"held_out_participant_in_training_room_{p}"
                elif p == val_participant:
                    assigned_split = "val"
                    reason = None
                elif p in train_p_list:
                    assigned_split = "train"
                    reason = None
                else:
                    assigned_split = "excluded"
                    reason = f"unassigned_participant_{p}"

            s_copy["split"] = assigned_split
            if reason:
                s_copy["exclusion_reason"] = reason
                exclusion_reasons[reason] = exclusion_reasons.get(reason, 0) + 1

            partitioned_sessions.append(s_copy)
            split_counts[assigned_split] += 1
            split_events[assigned_split].add(evt)
            if assigned_split == "excluded":
                split_windows["excluded"][act] = split_windows["excluded"].get(act, 0) + wins
            else:
                split_windows[assigned_split][act] += wins

        # Coverage checks
        train_classes = set(k for k, v in split_windows["train"].items() if v > 0)
        val_classes = set(k for k, v in split_windows["val"].items() if v > 0)
        test_classes = set(k for k, v in split_windows["test"].items() if v > 0)

        missing_in_train = set(target_classes) - train_classes
        missing_in_val = set(target_classes) - val_classes
        missing_in_test = set(target_classes) - test_classes

        if missing_in_train:
            raise InadequateClassCoverageError(f"Training partition missing classes: {sorted(list(missing_in_train))}")
        if missing_in_val:
            raise InadequateClassCoverageError(f"Validation partition missing classes: {sorted(list(missing_in_val))}")
        if missing_in_test:
            raise InadequateClassCoverageError(f"Test partition missing classes: {sorted(list(missing_in_test))}")

        # Invariant Assertions
        train_rooms = {s.get("room") for s in partitioned_sessions if s["split"] == "train"}
        val_rooms = {s.get("room") for s in partitioned_sessions if s["split"] == "val"}
        test_rooms = {s.get("room") for s in partitioned_sessions if s["split"] == "test"}
        assert test_room not in train_rooms, f"Test room {test_room} leaked into train partition!"
        assert test_room not in val_rooms, f"Test room {test_room} leaked into val partition!"
        assert test_rooms == {test_room}, f"Test partition contains non-test rooms: {test_rooms}"

        train_p_actual = {s.get("participant_id") for s in partitioned_sessions if s["split"] == "train"}
        val_p_actual = {s.get("participant_id") for s in partitioned_sessions if s["split"] == "val"}
        test_p_actual = {s.get("participant_id") for s in partitioned_sessions if s["split"] == "test"}
        assert test_participant not in train_p_actual, f"Test participant {test_participant} leaked into train!"
        assert test_participant not in val_p_actual, f"Test participant {test_participant} leaked into val!"
        assert test_p_actual == {test_participant}, f"Test partition contains non-test participants: {test_p_actual}"

        assert len(split_events["train"] & split_events["test"]) == 0, "Event leakage between train and test"
        assert len(split_events["train"] & split_events["val"]) == 0, "Event leakage between train and val"
        assert len(split_events["val"] & split_events["test"]) == 0, "Event leakage between val and test"

        new_manifest = dict(self.manifest)
        new_manifest["split_protocol"] = "Strict Room-Held-Out & Subject-Held-Out (Five-Class)"
        new_manifest["held_out_room"] = test_room
        new_manifest["test_participant"] = test_participant
        new_manifest["val_participant"] = val_participant
        new_manifest["train_participants"] = train_p_list
        new_manifest["target_classes"] = target_classes

        new_manifest["splits_summary"] = {
            "train_participants": train_p_list,
            "val_participants": [val_participant],
            "test_participants": [test_participant],
            "held_out_room": test_room,
            "train_sessions": split_counts["train"],
            "val_sessions": split_counts["val"],
            "test_sessions": split_counts["test"],
            "excluded_sessions": split_counts["excluded"],
            "train_windows": sum(split_windows["train"].values()),
            "val_windows": sum(split_windows["val"].values()),
            "test_windows": sum(split_windows["test"].values()),
            "excluded_windows": sum(split_windows["excluded"].values()),
            "total_sessions": len(partitioned_sessions),
            "total_windows": (
                sum(split_windows["train"].values())
                + sum(split_windows["val"].values())
                + sum(split_windows["test"].values())
                + sum(split_windows["excluded"].values())
            ),
            "windows_by_activity": {
                "train": split_windows["train"],
                "val": split_windows["val"],
                "test": split_windows["test"],
                "excluded": split_windows["excluded"]
            },
            "exclusion_reasons": exclusion_reasons
        }
        new_manifest["sessions"] = partitioned_sessions

        if output_manifest_path:
            output_manifest_path = Path(output_manifest_path)
            with open(output_manifest_path, "w", encoding="utf-8") as f:
                json.dump(new_manifest, f, indent=2)

        return new_manifest
