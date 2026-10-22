"""
CSIFormer Phase 58.3 — Passive Evidence Recorder Implementation.

Architecture:
- Implements an auditable JSON Lines (JSONL) telemetry recorder for ESP32-S3 serial streams.
- Designed to run against synthetic lines/fixtures offline or against live serial when authorized.
- Strictly isolated from canonical dataset storage (writes only to reports/evidence/).
- Enforces explicit per-line parsing status:
    * VALID_TARGET
    * FILTERED_NON_TARGET
    * PARSER_ERROR
    * NON_CSI_LINE
- Provides atomic manifest generation and streaming disk flush.

Persistence Note on flush():
- f.flush() flushes Python runtime internal buffers into the operating system kernel cache.
- To ensure durable physical persistence on disk (surviving OS kernel crashes or power failure),
  os.fsync(f.fileno()) must be explicitly called. This implementation calls flush() on every
  written record and provides sync_to_disk=True (os.fsync) on demand and at clean shutdown.
"""

import sys
import os
import time
import json
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Iterable

# Add project root and backend to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend"))
sys.path.insert(0, str(PROJECT_ROOT))

from app.services.real_csi_collector import RealCSICollector

DEFAULT_TARGET_MAC = "98:BA:5F:EF:28:26"
DEFAULT_EVIDENCE_DIR = PROJECT_ROOT / "reports" / "evidence"


class PassiveEvidenceRecorder:
    """
    Standardized, auditable evidence recorder for CSI serial telemetry.
    Can record from live serial or injected mock/synthetic line iterators.
    """

    def __init__(
        self,
        output_dir: Optional[Path] = None,
        target_mac: str = DEFAULT_TARGET_MAC,
        session_id: Optional[str] = None,
        overwrite: bool = False,
        sync_to_disk: bool = False,
    ):
        self.output_dir = Path(output_dir) if output_dir else DEFAULT_EVIDENCE_DIR
        self.target_mac = target_mac.upper().strip()
        self.overwrite = overwrite
        self.sync_to_disk = sync_to_disk

        timestamp_str = time.strftime("%Y%m%d_%H%M%S", time.gmtime())
        self.session_id = session_id or f"phase58_passive_repro_{timestamp_str}"

        # Prevent accidental contamination of canonical research dataset
        canonical_dataset_dir = (PROJECT_ROOT / "data" / "real_csi_dataset").resolve()
        if canonical_dataset_dir in self.output_dir.resolve().parents or self.output_dir.resolve() == canonical_dataset_dir:
            raise ValueError(
                f"Safety Violation: Evidence recorder must NOT write to canonical dataset directory: {self.output_dir}"
            )

        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.jsonl_path = self.output_dir / f"{self.session_id}_records.jsonl"
        self.manifest_path = self.output_dir / f"{self.session_id}_manifest.json"

        if not self.overwrite and (self.jsonl_path.exists() or self.manifest_path.exists()):
            raise FileExistsError(
                f"Evidence file already exists and overwrite=False: {self.jsonl_path}"
            )

        # Internal collector instance for standardized format parsing
        self.collector = RealCSICollector(
            target_mac=self.target_mac,
            filter_by_mac=True
        )

        # File handle and streaming state
        self._file_handle = open(self.jsonl_path, "w", encoding="utf-8")
        self.is_finalized = False

        # Counters and metrics
        self.line_index = 0
        self.total_lines_read = 0
        self.candidate_records = 0
        self.valid_records_parsed = 0
        self.valid_target_records = 0
        self.filtered_non_target_records = 0
        self.parser_errors = 0
        self.non_csi_lines = 0

        # Sequence tracking
        self.last_fw_seq: Optional[int] = None
        self.firmware_sequence_gaps = 0
        self.last_target_seq: Optional[int] = None
        self.target_sequence_gaps = 0
        self.duplicate_packets = 0
        self.out_of_order_packets = 0
        self.counter_resets = 0

        # Timing tracking
        self.start_wall: Optional[float] = None
        self.stop_wall: Optional[float] = None
        self.start_monotonic: Optional[float] = None
        self.stop_monotonic: Optional[float] = None
        self.last_arrival_monotonic: Optional[float] = None

        self.source_mac_counts: Dict[str, int] = {}
        self.sample_lines: List[str] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not self.is_finalized:
            self.finalize()

    @staticmethod
    def decode_raw_bytes(raw_bytes: bytes, buffer: str = "") -> Tuple[List[str], str]:
        """
        Decodes incoming raw byte chunks into complete newline-delimited lines.
        Uses errors='replace' to prevent unhandled UnicodeDecodeErrors on corrupted UART bytes.
        Returns a tuple of (complete_lines, remaining_buffer).
        """
        text = raw_bytes.decode("utf-8", errors="replace")
        combined = buffer + text
        complete_lines = []
        while "\n" in combined:
            line, combined = combined.split("\n", 1)
            complete_lines.append(line)
        return complete_lines, combined

    def process_line(
        self,
        raw_line: str,
        host_monotonic: Optional[float] = None,
        host_wall: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Processes a single serial line, determines its classification,
        updates internal counters, and streams the record to the JSONL evidence file.
        """
        if self.is_finalized:
            raise RuntimeError("Cannot process line on a finalized evidence recorder.")

        now_mono = time.perf_counter() if host_monotonic is None else host_monotonic
        now_wall = time.time() if host_wall is None else host_wall

        if self.start_monotonic is None:
            self.start_monotonic = now_mono
            self.start_wall = now_wall

        self.stop_monotonic = now_mono
        self.stop_wall = now_wall

        self.line_index += 1
        self.total_lines_read += 1

        inter_arrival = (
            now_mono - self.last_arrival_monotonic
            if self.last_arrival_monotonic is not None
            else 0.0
        )
        self.last_arrival_monotonic = now_mono

        # Normalize line: strip trailing CR/LF while preserving raw serial payload
        clean_line = raw_line.rstrip("\r\n")

        if len(self.sample_lines) < 10:
            self.sample_lines.append(clean_line[:120])

        # Classification
        parse_status = "NON_CSI_LINE"
        rejection_reason = None
        parsed_fields = None

        if not clean_line.strip():
            parse_status = "NON_CSI_LINE"
            rejection_reason = "empty_line"
            self.non_csi_lines += 1
        else:
            is_candidate = ("RSSI=" in clean_line and "CSI:" in clean_line) or clean_line.startswith("CSI_DATA")
            if not is_candidate:
                parse_status = "NON_CSI_LINE"
                rejection_reason = "non_candidate_prefix"
                self.non_csi_lines += 1
            else:
                self.candidate_records += 1
                try:
                    parsed = self.collector.parse_raw_telemetry_line(clean_line)
                except Exception as e:
                    parsed = None
                    rejection_reason = f"parser_exception:{type(e).__name__}"

                if parsed is None:
                    parse_status = "PARSER_ERROR"
                    if rejection_reason is None:
                        rejection_reason = "invalid_token_format_or_subcarrier_split"
                    self.parser_errors += 1
                else:
                    self.valid_records_parsed += 1
                    mac = str(parsed.get("mac", "")).upper()
                    rssi = parsed.get("rssi")
                    noise = parsed.get("noise_floor")
                    seq = parsed.get("sequence")
                    num_sc = parsed.get("num_subcarriers")

                    self.source_mac_counts[mac] = self.source_mac_counts.get(mac, 0) + 1

                    # Sequence continuity tracking on parsed frames
                    if seq is not None:
                        self._track_firmware_sequence(seq)

                    is_target = (mac == self.target_mac)
                    if is_target:
                        parse_status = "VALID_TARGET"
                        rejection_reason = None
                        self.valid_target_records += 1
                        if seq is not None:
                            self._track_target_sequence(seq)
                    else:
                        parse_status = "FILTERED_NON_TARGET"
                        rejection_reason = f"non_target_mac:{mac}"
                        self.filtered_non_target_records += 1

                    parsed_fields = {
                        "protocol": self.collector.detected_protocol or "structured_csi_data",
                        "mac": mac,
                        "is_target": is_target,
                        "rssi": rssi,
                        "noise_floor": noise,
                        "firmware_sequence": seq,
                        "raw_subcarrier_count": num_sc,
                    }

        record = {
            "line_index": self.line_index,
            "host_monotonic_time": round(now_mono, 6),
            "host_wall_time": round(now_wall, 6),
            "inter_arrival_host_s": round(inter_arrival, 6),
            "raw_serial_line": clean_line,
            "parse_status": parse_status,
            "rejection_reason": rejection_reason,
            "parsed_fields": parsed_fields,
        }

        # Write to JSON Lines stream
        self._file_handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        self._file_handle.flush()
        if self.sync_to_disk:
            try:
                os.fsync(self._file_handle.fileno())
            except OSError:
                pass

        return record

    def _track_firmware_sequence(self, seq: int):
        """Monitors continuity across all valid parsed frames."""
        if self.last_fw_seq is not None:
            if seq > self.last_fw_seq:
                gap = seq - (self.last_fw_seq + 1)
                if gap > 0:
                    self.firmware_sequence_gaps += gap
                self.last_fw_seq = seq
            elif seq < self.last_fw_seq:
                if self.last_fw_seq > 0xFFFF0000 and seq < 0x10000:
                    # 32-bit unsigned overflow wrap
                    gap = (seq + 0x100000000) - (self.last_fw_seq + 1)
                    if gap > 0:
                        self.firmware_sequence_gaps += gap
                    self.last_fw_seq = seq
                elif (self.last_fw_seq - seq) > 1000 or (self.last_fw_seq >= 100 and seq <= 10):
                    self.counter_resets += 1
                    self.last_fw_seq = seq
                else:
                    self.out_of_order_packets += 1
            else:
                self.duplicate_packets += 1
        else:
            self.last_fw_seq = seq

    def _track_target_sequence(self, seq: int):
        """Monitors sequence jumps in target-only stream."""
        if self.last_target_seq is not None:
            if seq > self.last_target_seq:
                t_gap = seq - (self.last_target_seq + 1)
                if t_gap > 0:
                    self.target_sequence_gaps += t_gap
            elif seq < self.last_target_seq:
                if self.last_target_seq > 0xFFFF0000 and seq < 0x10000:
                    t_gap = (seq + 0x100000000) - (self.last_target_seq + 1)
                    if t_gap > 0:
                        self.target_sequence_gaps += t_gap
        self.last_target_seq = seq

    def process_stream(
        self,
        line_iterable: Iterable[str],
        max_duration_s: Optional[float] = None,
        max_lines: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Processes an iterable stream of lines (e.g. from mock serial or file generator).
        Stops when iterable is exhausted, duration exceeds max_duration_s, or max_lines reached.
        """
        start_perf = time.perf_counter()
        for raw_line in line_iterable:
            self.process_line(raw_line)
            if max_lines and self.total_lines_read >= max_lines:
                break
            if max_duration_s and (time.perf_counter() - start_perf) >= max_duration_s:
                break

        return self.finalize()

    def finalize(self, port_released: Optional[bool] = None) -> Dict[str, Any]:
        """
        Flushes and closes the JSONL file, computes its cryptographic MD5,
        and atomically writes the companion session manifest.
        """
        if self.is_finalized:
            return self.get_summary()

        self.is_finalized = True

        # Flush runtime buffers and force OS sync
        self._file_handle.flush()
        try:
            os.fsync(self._file_handle.fileno())
        except OSError:
            pass
        self._file_handle.close()

        # Compute cryptographic hash of the raw JSONL file
        with open(self.jsonl_path, "rb") as f:
            file_md5 = hashlib.md5(f.read()).hexdigest()

        dur_s = (
            (self.stop_monotonic - self.start_monotonic)
            if (self.start_monotonic is not None and self.stop_monotonic is not None)
            else 0.0
        )
        target_rate = round(self.valid_target_records / dur_s, 4) if dur_s > 0 else 0.0
        agg_rate = round(self.valid_records_parsed / dur_s, 4) if dur_s > 0 else 0.0
        parse_fraction = (
            round(self.valid_records_parsed / self.candidate_records, 4)
            if self.candidate_records > 0
            else 1.0
        )

        manifest = {
            "session_id": self.session_id,
            "target_mac": self.target_mac,
            "timing": {
                "start_wall": self.start_wall,
                "stop_wall": self.stop_wall,
                "start_monotonic": self.start_monotonic,
                "stop_monotonic": self.stop_monotonic,
                "actual_duration_s": round(dur_s, 4),
            },
            "counts": {
                "total_lines_read": self.total_lines_read,
                "candidate_records": self.candidate_records,
                "valid_records_parsed": self.valid_records_parsed,
                "valid_target_records": self.valid_target_records,
                "filtered_non_target_records": self.filtered_non_target_records,
                "parser_errors": self.parser_errors,
                "non_csi_lines": self.non_csi_lines,
            },
            "sequence_reconciliation": {
                "firmware_sequence_gaps": self.firmware_sequence_gaps,
                "target_sequence_gaps": self.target_sequence_gaps,
                "counter_resets": self.counter_resets,
                "out_of_order_packets": self.out_of_order_packets,
                "duplicate_packets": self.duplicate_packets,
            },
            "rates": {
                "target_rate_hz": target_rate,
                "aggregate_rate_hz": agg_rate,
                "candidate_parse_fraction": parse_fraction,
            },
            "source_mac_distribution": self.source_mac_counts,
            "evidence_file": self.jsonl_path.name,
            "evidence_file_md5": file_md5,
            "port_released": port_released,
        }

        # Atomic persistence of manifest
        tmp_manifest = self.manifest_path.with_suffix(".json.tmp")
        with open(tmp_manifest, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                pass
        os.replace(tmp_manifest, self.manifest_path)

        return manifest

    def get_summary(self) -> Dict[str, Any]:
        """Reads and returns the manifest if finalized, else returns current state."""
        if self.manifest_path.exists():
            with open(self.manifest_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {
            "session_id": self.session_id,
            "total_lines_read": self.total_lines_read,
            "is_finalized": self.is_finalized,
        }


def run_hardware_capture(
    port: str = "COM5",
    baud_rate: int = 115200,
    duration_s: float = 30.0,
    target_mac: str = DEFAULT_TARGET_MAC,
    output_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Executes a hardware passive capture on COM5 when EXPLICITLY AUTHORIZED.
    Strictly read-only: dtr=False, rts=False, zero writes.
    """
    import serial

    recorder = PassiveEvidenceRecorder(output_dir=output_dir, target_mac=target_mac)

    ser = serial.Serial()
    ser.port = port
    ser.baudrate = baud_rate
    ser.timeout = 0.1
    ser.write_timeout = 1.0
    ser.dtr = False
    ser.rts = False
    ser.open()
    ser.reset_input_buffer()

    start_perf = time.perf_counter()
    end_perf = start_perf + duration_s
    line_buffer = ""

    try:
        while time.perf_counter() < end_perf:
            in_w = ser.in_waiting or 1
            raw_bytes = ser.read(in_w)
            if not raw_bytes:
                continue

            lines, line_buffer = recorder.decode_raw_bytes(raw_bytes, line_buffer)
            for line in lines:
                if line.strip():
                    recorder.process_line(line)
    finally:
        ser.close()
        port_released = not ser.is_open

    return recorder.finalize(port_released=port_released)


if __name__ == "__main__":
    print("CSIFormer Phase 58.3 Evidence Recorder")
    print("NOTE: Hardware capture is on HOLD pending explicit authorization.")
    print("Use backend/tests/test_phase58_evidence_recorder.py to run offline tests.")
