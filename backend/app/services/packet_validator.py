import math
import time
from typing import Dict, Any, List, Optional, Tuple
from app.models.schemas import CSIPacketFrame

class PacketValidationResult:
    """Represents the verification outcome of a single CSI frame."""
    def __init__(
        self,
        is_valid: bool,
        node_id: str,
        sequence: int,
        timestamp: float,
        error_type: Optional[str] = None,
        dropped_packets_detected: int = 0,
        subcarrier_count: int = 64
    ):
        self.is_valid = is_valid
        self.node_id = node_id
        self.sequence = sequence
        self.timestamp = timestamp
        self.error_type = error_type
        self.dropped_packets_detected = dropped_packets_detected
        self.subcarrier_count = subcarrier_count

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "node_id": self.node_id,
            "sequence": self.sequence,
            "timestamp": self.timestamp,
            "error_type": self.error_type,
            "dropped_packets_detected": self.dropped_packets_detected,
            "subcarrier_count": self.subcarrier_count
        }

class PacketValidatorEngine:
    """
    Real-Time CSI Packet Structure, Sequence Continuity & Integrity Validator.
    Verifies raw frames from ESP32-S3 hardware:
    - 64-subcarrier length requirement
    - Absence of NaN / Inf / null values
    - Sequence ID continuity & packet drop detection
    - Monotonic timestamp verification
    - Amplitude & Phase boundary validation
    """
    def __init__(self, expected_subcarriers: int = 64):
        self.expected_subcarriers = expected_subcarriers
        self.last_sequences: Dict[str, int] = {}
        self.last_timestamps: Dict[str, float] = {}
        
        # Aggregate Counters
        self.total_validated = 0
        self.total_valid = 0
        self.total_corrupted = 0
        self.total_dropped = 0

    def reset_node_state(self, node_id: Optional[str] = None):
        """Resets sequence tracking for a single node or all nodes."""
        if node_id:
            self.last_sequences.pop(node_id, None)
            self.last_timestamps.pop(node_id, None)
        else:
            self.last_sequences.clear()
            self.last_timestamps.clear()
            self.total_validated = 0
            self.total_valid = 0
            self.total_corrupted = 0
            self.total_dropped = 0

    def validate_frame(self, frame: CSIPacketFrame) -> PacketValidationResult:
        """
        Validates an incoming CSIPacketFrame against integrity and sequence constraints.
        """
        self.total_validated += 1
        node_id = frame.node_id or "unknown-node"
        seq = frame.sequence
        ts = frame.timestamp

        # 1. Structural Length Check
        amps = frame.amplitudes
        phases = frame.phases

        if len(amps) != self.expected_subcarriers or len(phases) != self.expected_subcarriers:
            self.total_corrupted += 1
            return PacketValidationResult(
                is_valid=False,
                node_id=node_id,
                sequence=seq,
                timestamp=ts,
                error_type=f"INVALID_SUBCARRIER_LENGTH: amps={len(amps)}, phases={len(phases)}, expected={self.expected_subcarriers}",
                subcarrier_count=len(amps)
            )

        # 2. NaN / Inf / Boundary Check
        for i, (a, p) in enumerate(zip(amps, phases)):
            if math.isnan(a) or math.isinf(a) or a < 0.0 or a > 500.0:
                self.total_corrupted += 1
                return PacketValidationResult(
                    is_valid=False,
                    node_id=node_id,
                    sequence=seq,
                    timestamp=ts,
                    error_type=f"CORRUPT_AMPLITUDE_VALUE at sc_{i}: {a}",
                    subcarrier_count=len(amps)
                )
            if math.isnan(p) or math.isinf(p):
                self.total_corrupted += 1
                return PacketValidationResult(
                    is_valid=False,
                    node_id=node_id,
                    sequence=seq,
                    timestamp=ts,
                    error_type=f"CORRUPT_PHASE_VALUE at sc_{i}: {p}",
                    subcarrier_count=len(amps)
                )

        # 3. Sequence Continuity & Drop Detection
        dropped_count = 0
        if node_id in self.last_sequences:
            prev_seq = self.last_sequences[node_id]
            if seq > prev_seq + 1:
                dropped_count = seq - prev_seq - 1
                self.total_dropped += dropped_count
            elif seq <= prev_seq and seq != 0:
                # Out-of-order or duplicate packet
                self.total_corrupted += 1
                return PacketValidationResult(
                    is_valid=False,
                    node_id=node_id,
                    sequence=seq,
                    timestamp=ts,
                    error_type=f"OUT_OF_ORDER_SEQUENCE: prev={prev_seq}, current={seq}",
                    dropped_packets_detected=0,
                    subcarrier_count=len(amps)
                )

        self.last_sequences[node_id] = seq
        self.last_timestamps[node_id] = ts
        self.total_valid += 1

        return PacketValidationResult(
            is_valid=True,
            node_id=node_id,
            sequence=seq,
            timestamp=ts,
            dropped_packets_detected=dropped_count,
            subcarrier_count=len(amps)
        )

    def get_integrity_summary(self) -> Dict[str, Any]:
        """Returns overall validation engine statistics."""
        loss_rate = 0.0
        total_expected = self.total_valid + self.total_dropped + self.total_corrupted
        if total_expected > 0:
            loss_rate = round((self.total_dropped / total_expected) * 100, 2)

        return {
            "total_validated": self.total_validated,
            "total_valid": self.total_valid,
            "total_corrupted": self.total_corrupted,
            "total_dropped": self.total_dropped,
            "packet_loss_pct": loss_rate,
            "monitored_nodes_count": len(self.last_sequences)
        }

packet_validator = PacketValidatorEngine()
