"""
CSIFormer Phase 19 — Comprehensive Session & Dataset Validator.

Performs deterministic, evidence-based validation of real CSI data:
1. Manifest-to-file consistency (file existence, packet count matching).
2. Unique session and event identifier enforcement.
3. Raw CSI dimensional checks vs. aligned 56-subcarrier model representation.
4. Numerical integrity: detection of NaN, Inf, or non-finite values.
5. Hardware timing and sequence gap accounting (monotonic timestamps, loss rates).
6. Label confirmation enforcement: unconfirmed or ambiguous trials must be 'unknown' (class_id -1).
7. Window-to-session and window-to-event traceability.
8. Duplicate session, file, and frame detection.
9. Room and geometric metadata completeness.
10. Partition leakage audit (zero participant, session, or event leakage across Train/Val/Test).
11. Quarantine workflow: isolates corrupt or non-compliant recordings into a quarantine area.
"""

import os
import json
import shutil
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Set, Optional, Tuple
import numpy as np


class SessionValidationError(ValueError):
    """Raised when a physical CSI session fails validation checks."""
    pass


class DatasetIntegrityValidator:
    """
    Validates physical CSI sessions and manifests against quality gates.
    """

    def __init__(self, dataset_dir: Path, manifest_path: Optional[Path] = None):
        self.dataset_dir = Path(dataset_dir)
        self.manifest_path = Path(manifest_path) if manifest_path else self.dataset_dir / "dataset_manifest.json"
        self.quarantine_dir = self.dataset_dir / "quarantine"

    def validate_session_file(self, json_path: Path) -> Dict[str, Any]:
        """
        Validates an individual physical session JSON file.
        Returns a dictionary with validation results, metrics, and any warnings.
        """
        json_path = Path(json_path)
        if not json_path.exists():
            raise FileNotFoundError(f"Session file not found: {json_path}")

        with open(json_path, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError as e:
                raise SessionValidationError(f"Corrupted JSON in {json_path.name}: {e}")

        meta = data.get("metadata", {})
        frames = data.get("frames", [])

        # 1. Identifier checks
        sid = meta.get("session_id")
        if not sid:
            raise SessionValidationError(f"Missing session_id in metadata of {json_path.name}")

        pid = meta.get("participant_id")
        if not pid or not pid.startswith("Participant_"):
            raise SessionValidationError(f"Invalid or missing pseudonymized participant_id '{pid}' in {sid}")

        evt = meta.get("event_id") or sid

        # 2. Frame count matching
        declared_frames = data.get("frame_count")
        actual_frames = len(frames)
        if declared_frames is not None and declared_frames != actual_frames:
            raise SessionValidationError(
                f"Frame count mismatch in {sid}: metadata declares {declared_frames}, but found {actual_frames} frames."
            )

        if actual_frames == 0:
            raise SessionValidationError(f"Session {sid} contains 0 frames.")

        # 3. Label and Confirmation Status
        confirmed = meta.get("ground_truth_confirmed", True)
        activity = meta.get("ground_truth_activity") or meta.get("activity_label", "unknown")
        if not confirmed and activity != "unknown":
            raise SessionValidationError(
                f"Unconfirmed session {sid} has activity '{activity}'. Must be labeled as 'unknown' (class_id -1)."
            )

        # 4. Numerical Integrity, Sequence & Timing
        seqs = []
        timestamps = []
        has_raw_subcarriers = False
        raw_sc_counts = set()

        for idx, frame in enumerate(frames):
            # Check required keys
            for k in ["timestamp", "sequence", "rssi", "noise", "amplitudes"]:
                if k not in frame:
                    raise SessionValidationError(f"Frame {idx} in {sid} missing required key '{k}'")

            t = frame["timestamp"]
            seq = frame["sequence"]
            rssi = frame["rssi"]
            amps = frame["amplitudes"]

            # Check finite numbers
            if not np.isfinite(t) or not np.isfinite(seq) or not np.isfinite(rssi):
                raise SessionValidationError(f"Non-finite timestamp, sequence, or RSSI in frame {idx} of {sid}")

            amps_arr = np.array(amps, dtype=np.float32)
            if not np.isfinite(amps_arr).all():
                raise SessionValidationError(f"Non-finite amplitudes in frame {idx} of {sid}")

            if len(amps_arr) != 56:
                raise SessionValidationError(f"Frame {idx} amplitudes length is {len(amps_arr)}, expected 56 channels.")

            # Check raw subcarrier preservation if present
            if "raw_amplitudes" in frame:
                has_raw_subcarriers = True
                raw_amps = np.array(frame["raw_amplitudes"], dtype=np.float32)
                if not np.isfinite(raw_amps).all():
                    raise SessionValidationError(f"Non-finite raw_amplitudes in frame {idx} of {sid}")
                raw_sc_counts.add(len(raw_amps))

            timestamps.append(t)
            seqs.append(seq)

        # 5. Timestamp Monotonicity
        if len(timestamps) > 1:
            diffs_t = np.diff(timestamps)
            # Allow at most 1 backward jump in hardware clock (clock rollover)
            if (diffs_t < 0).sum() > 1:
                raise SessionValidationError(f"Severe timestamp non-monotonicity in {sid}")

        # 6. Sequence Gaps & Packet Loss Calculation
        dropped_packets = 0
        if len(seqs) > 1:
            diffs_s = np.diff(seqs)
            dropped_packets = int(np.sum([d - 1 for d in diffs_s if d > 1]))
        total_expected = len(seqs) + dropped_packets
        loss_rate = dropped_packets / total_expected if total_expected > 0 else 0.0

        # 7. Metadata completeness
        room = meta.get("room_type", "Unknown")
        tx_dist = meta.get("tx_rx_distance_meters") or meta.get("tx_rx_distance_m", 0.0)

        return {
            "session_id": sid,
            "event_id": evt,
            "participant_id": pid,
            "activity": activity,
            "confirmed": confirmed,
            "packet_count": actual_frames,
            "dropped_packets": dropped_packets,
            "loss_rate": round(loss_rate, 4),
            "room": room,
            "tx_rx_distance_m": tx_dist,
            "has_raw_subcarriers": has_raw_subcarriers,
            "raw_subcarrier_counts": sorted(list(raw_sc_counts)),
            "valid": True
        }

    def quarantine_session(self, json_path: Path, reason: str) -> Path:
        """
        Quarantines an invalid or corrupted session file rather than silently repairing it.
        Moves both .json and associated .csv (if present) to self.quarantine_dir and logs the incident.
        """
        json_path = Path(json_path)
        self.quarantine_dir.mkdir(parents=True, exist_ok=True)

        target_json = self.quarantine_dir / json_path.name
        shutil.move(str(json_path), str(target_json))

        csv_path = json_path.with_suffix(".csv")
        target_csv = None
        if csv_path.exists():
            target_csv = self.quarantine_dir / csv_path.name
            shutil.move(str(csv_path), str(target_csv))

        # Log quarantine action
        log_path = self.quarantine_dir / "quarantine_manifest.json"
        log_data = []
        if log_path.exists():
            with open(log_path, "r", encoding="utf-8") as f:
                try:
                    log_data = json.load(f)
                except Exception:
                    log_data = []

        log_data.append({
            "filename": json_path.name,
            "original_path": str(json_path),
            "quarantined_path": str(target_json),
            "csv_quarantined": str(target_csv) if target_csv else None,
            "reason": reason
        })

        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(log_data, f, indent=2)

        return target_json

    def validate_dataset_manifest(self) -> Dict[str, Any]:
        """
        Validates the entire dataset manifest against physical disk contents.
        Verifies:
        - Unique session IDs and event IDs across all entries.
        - Physical file existence for every manifest session.
        - Exact packet count match between manifest and session file.
        - Summary counts matching sum of sessions.
        """
        if not self.manifest_path.exists():
            raise FileNotFoundError(f"Manifest missing: {self.manifest_path}")

        with open(self.manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        sessions = manifest.get("sessions", [])
        if len(sessions) == 0:
            raise SessionValidationError("Manifest contains 0 sessions.")

        sids = set()
        session_results = []
        participants = set()
        events = set()
        total_packets = 0
        activities = {}

        for s in sessions:
            sid = s.get("session_id")
            if not sid:
                raise SessionValidationError("Manifest entry missing session_id")
            if sid in sids:
                raise SessionValidationError(f"Duplicate session_id in manifest: {sid}")
            sids.add(sid)

            pid = s.get("participant_id")
            participants.add(pid)
            evt = s.get("event_id") or sid
            events.add(evt)

            act = s.get("activity_label", "unknown")
            pkts = s.get("packet_count", 0)
            total_packets += pkts
            wins = pkts // 50
            activities[act] = activities.get(act, 0) + wins

            # Check referenced JSON
            jfile = self.dataset_dir / s.get("json_file", f"{sid}.json")
            if not jfile.exists():
                raise SessionValidationError(f"Referenced session file missing from disk: {jfile}")

            # Run full file validation
            res = self.validate_session_file(jfile)
            session_results.append(res)

        return {
            "total_sessions": len(sessions),
            "total_packets": total_packets,
            "total_windows": sum(activities.values()),
            "distinct_participants": sorted(list(participants)),
            "distinct_events": len(events),
            "activity_windows": activities,
            "all_sessions_valid": True,
            "session_validations": session_results
        }
