"""
CSIFormer Phase 58.3 — Offline Evidence Recorder Unit Tests.

Validates the JSONL evidence recorder infrastructure strictly offline.
Zero hardware communication, zero serial port opening, zero network traffic, zero model inference.
"""

import sys
import os
import json
import hashlib
import tempfile
from pathlib import Path
import pytest

# Ensure project root and backend are on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend"))
sys.path.insert(0, str(PROJECT_ROOT))

from scratch.run_phase58_stage1_repro_evidence import PassiveEvidenceRecorder
from app.services.real_csi_collector import RealCSICollector

# Synthetic fixtures
TARGET_MAC = "98:BA:5F:EF:28:26"
AMBIENT_MAC = "00:2D:F4:5B:4B:7D"

VALID_TARGET_LINE = (
    f"CSI_DATA,{TARGET_MAC},-55,-93,6129,64,"
    + ",".join([f"{10.0 + i*0.1:.2f}:{0.5:.3f}" for i in range(64)])
)

VALID_NON_TARGET_LINE = (
    f"CSI_DATA,{AMBIENT_MAC},-61,-93,6130,64,"
    + ",".join([f"{5.0 + i*0.1:.2f}:{-0.2:.3f}" for i in range(64)])
)

MALFORMED_CSI_LINE_SHORT = f"CSI_DATA,{TARGET_MAC},-50"
MALFORMED_CSI_LINE_GARBAGE = f"CSI_DATA,{TARGET_MAC},not_a_number,noise,seq,num_sc,garbage"

BOOT_LOG_LINE = "I (812) ESP32S3_CSI_COLLECTOR: Wi-Fi CSI Collection Enabled on Channel 7"
RST_LINE = "rst:0x1 (POWERON_RESET),boot:0x8 (SPI_FAST_FLASH_BOOT)"


@pytest.fixture
def temp_evidence_dir(tmp_path):
    """Provides an isolated temporary directory for evidence files."""
    ev_dir = tmp_path / "evidence"
    ev_dir.mkdir(parents=True, exist_ok=True)
    return ev_dir


def test_valid_target_record(temp_evidence_dir):
    """Test 1: Valid target CSI line is classified as VALID_TARGET and parsed correctly."""
    with PassiveEvidenceRecorder(output_dir=temp_evidence_dir, target_mac=TARGET_MAC) as rec:
        record = rec.process_line(VALID_TARGET_LINE, host_monotonic=100.0, host_wall=1700000000.0)

    assert record["parse_status"] == "VALID_TARGET"
    assert record["rejection_reason"] is None
    assert record["line_index"] == 1
    assert record["parsed_fields"]["mac"] == TARGET_MAC
    assert record["parsed_fields"]["is_target"] is True
    assert record["parsed_fields"]["rssi"] == -55
    assert record["parsed_fields"]["noise_floor"] == -93
    assert record["parsed_fields"]["firmware_sequence"] == 6129
    assert record["parsed_fields"]["raw_subcarrier_count"] == 64


def test_valid_non_target_record(temp_evidence_dir):
    """Test 2: Ambient Wi-Fi packet is filtered and classified as FILTERED_NON_TARGET."""
    with PassiveEvidenceRecorder(output_dir=temp_evidence_dir, target_mac=TARGET_MAC) as rec:
        record = rec.process_line(VALID_NON_TARGET_LINE)

    assert record["parse_status"] == "FILTERED_NON_TARGET"
    assert record["rejection_reason"] == f"non_target_mac:{AMBIENT_MAC}"
    assert record["parsed_fields"]["is_target"] is False
    assert record["parsed_fields"]["mac"] == AMBIENT_MAC


def test_malformed_csi_records(temp_evidence_dir):
    """Test 3: Candidate CSI lines with malformed syntax trigger PARSER_ERROR."""
    with PassiveEvidenceRecorder(output_dir=temp_evidence_dir, target_mac=TARGET_MAC) as rec:
        r1 = rec.process_line(MALFORMED_CSI_LINE_SHORT)
        r2 = rec.process_line(MALFORMED_CSI_LINE_GARBAGE)

    assert r1["parse_status"] == "PARSER_ERROR"
    assert r1["rejection_reason"] is not None
    assert r1["parsed_fields"] is None

    assert r2["parse_status"] == "PARSER_ERROR"
    assert r2["rejection_reason"] is not None

    summary = rec.get_summary()
    assert summary["counts"]["parser_errors"] == 2


def test_non_csi_boot_log_lines(temp_evidence_dir):
    """Test 4: Non-CSI lines (boot logs, empty lines, debug) are tagged NON_CSI_LINE."""
    with PassiveEvidenceRecorder(output_dir=temp_evidence_dir, target_mac=TARGET_MAC) as rec:
        r1 = rec.process_line(BOOT_LOG_LINE)
        r2 = rec.process_line(RST_LINE)
        r3 = rec.process_line("")
        r4 = rec.process_line("   \r\n")

    assert r1["parse_status"] == "NON_CSI_LINE"
    assert r1["rejection_reason"] == "non_candidate_prefix"
    assert r2["parse_status"] == "NON_CSI_LINE"
    assert r3["parse_status"] == "NON_CSI_LINE"
    assert r3["rejection_reason"] == "empty_line"
    assert r4["parse_status"] == "NON_CSI_LINE"
    assert r4["rejection_reason"] == "empty_line"


def test_unicode_and_decoding_error_handling():
    """Test 5: Byte chunks with invalid UTF-8 sequences are decoded safely without error."""
    corrupted_bytes = b"\xff\xfe\x80CSI_DATA,98:BA:5F:EF:28:26,-55\nValidLine\nTrailingPartial"
    lines, remainder = PassiveEvidenceRecorder.decode_raw_bytes(corrupted_bytes, buffer="")

    assert len(lines) == 2
    assert "CSI_DATA" in lines[0]
    assert lines[1] == "ValidLine"
    assert remainder == "TrailingPartial"


def test_jsonl_roundtrip_validity(temp_evidence_dir):
    """Test 6: All records written to JSONL are valid JSON with complete required schema."""
    lines_to_feed = [
        VALID_TARGET_LINE,
        BOOT_LOG_LINE,
        VALID_NON_TARGET_LINE,
        MALFORMED_CSI_LINE_SHORT,
    ]

    with PassiveEvidenceRecorder(output_dir=temp_evidence_dir, target_mac=TARGET_MAC) as rec:
        for l in lines_to_feed:
            rec.process_line(l)

    jsonl_file = rec.jsonl_path
    assert jsonl_file.exists()

    with open(jsonl_file, "r", encoding="utf-8") as f:
        read_records = [json.loads(line) for line in f]

    assert len(read_records) == 4
    for idx, r in enumerate(read_records, start=1):
        assert r["line_index"] == idx
        assert "host_monotonic_time" in r
        assert "host_wall_time" in r
        assert "raw_serial_line" in r
        assert "parse_status" in r
        assert r["parse_status"] in ["VALID_TARGET", "FILTERED_NON_TARGET", "PARSER_ERROR", "NON_CSI_LINE"]


def test_sequential_line_indexes_and_count_reconciliation(temp_evidence_dir):
    """Test 7: Sequential line numbering and full mathematical count reconciliation."""
    stream = (
        [VALID_TARGET_LINE] * 10
        + [VALID_NON_TARGET_LINE] * 5
        + [BOOT_LOG_LINE] * 3
        + [MALFORMED_CSI_LINE_SHORT] * 2
    )

    with PassiveEvidenceRecorder(output_dir=temp_evidence_dir, target_mac=TARGET_MAC) as rec:
        manifest = rec.process_stream(stream)

    assert manifest["counts"]["total_lines_read"] == 20
    assert manifest["counts"]["valid_target_records"] == 10
    assert manifest["counts"]["filtered_non_target_records"] == 5
    assert manifest["counts"]["non_csi_lines"] == 3
    assert manifest["counts"]["parser_errors"] == 2
    assert manifest["counts"]["candidate_records"] == 17
    assert manifest["counts"]["valid_records_parsed"] == 15

    # Reconciliation formulas
    total = manifest["counts"]["total_lines_read"]
    c = manifest["counts"]
    assert c["valid_target_records"] + c["filtered_non_target_records"] == c["valid_records_parsed"]
    assert c["valid_records_parsed"] + c["parser_errors"] == c["candidate_records"]
    assert c["candidate_records"] + c["non_csi_lines"] == total

    # Hash verification
    with open(rec.jsonl_path, "rb") as f:
        expected_md5 = hashlib.md5(f.read()).hexdigest()
    assert manifest["evidence_file_md5"] == expected_md5


def test_interrupted_capture_and_clean_shutdown(temp_evidence_dir):
    """Test 8: Abrupt termination in context manager cleanly finalizes files and manifest."""
    rec = PassiveEvidenceRecorder(output_dir=temp_evidence_dir, target_mac=TARGET_MAC, session_id="test_abort")
    rec.process_line(VALID_TARGET_LINE)
    rec.process_line(VALID_NON_TARGET_LINE)

    # Simulate shutdown
    rec.finalize(port_released=True)

    assert rec.is_finalized is True
    assert rec.jsonl_path.exists()
    assert rec.manifest_path.exists()

    with open(rec.manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    assert manifest["port_released"] is True
    assert manifest["counts"]["total_lines_read"] == 2


def test_existing_collector_api_compatibility():
    """Test 9: RealCSICollector is compatible with the parsing and filtering expectations."""
    collector = RealCSICollector(target_mac=TARGET_MAC, filter_by_mac=True)
    parsed = collector.parse_raw_telemetry_line(VALID_TARGET_LINE)

    assert parsed is not None
    assert parsed["mac"] == TARGET_MAC
    assert parsed["rssi"] == -55
    assert len(parsed["raw_amplitudes"]) == 64
    assert len(parsed["raw_phases"]) == 64
    assert collector.detected_protocol == "structured_csi_data"


def test_dataset_directory_protection():
    """Test 10: Strict safety assertion prevents writing evidence to canonical dataset directory."""
    canonical_dir = PROJECT_ROOT / "data" / "real_csi_dataset"
    with pytest.raises(ValueError, match="Safety Violation"):
        PassiveEvidenceRecorder(output_dir=canonical_dir)

    nested_dir = canonical_dir / "evidence_subfolder"
    with pytest.raises(ValueError, match="Safety Violation"):
        PassiveEvidenceRecorder(output_dir=nested_dir)


def test_file_overwrite_protection(temp_evidence_dir):
    """Test 11: FileExistsError raised if evidence file already exists and overwrite=False."""
    session_id = "test_duplicate_session"
    rec1 = PassiveEvidenceRecorder(output_dir=temp_evidence_dir, session_id=session_id)
    rec1.process_line(VALID_TARGET_LINE)
    rec1.finalize()

    with pytest.raises(FileExistsError):
        PassiveEvidenceRecorder(output_dir=temp_evidence_dir, session_id=session_id, overwrite=False)


def test_valid_target_line_with_crlf_trailing(temp_evidence_dir):
    """Test 12: Lines with CRLF line endings are stripped cleanly and do not corrupt parsing."""
    raw_crlf_line = VALID_TARGET_LINE + "\r\n"
    with PassiveEvidenceRecorder(output_dir=temp_evidence_dir, target_mac=TARGET_MAC) as rec:
        rec.process_line(raw_crlf_line)

    with open(rec.jsonl_path, "r", encoding="utf-8") as f:
        data = json.loads(f.readline())
    assert data["parse_status"] == "VALID_TARGET"
    assert data["raw_serial_line"] == VALID_TARGET_LINE
    assert data["raw_serial_line"].endswith("\r") is False
    assert data["raw_serial_line"].endswith("\n") is False


def test_sequence_gap_accounting_with_non_target_interleaving(temp_evidence_dir):
    """Test 13: Sequence gap tracking differentiates global firmware gaps from target gaps."""
    # Target frame at seq=100
    line1 = f"CSI_DATA,{TARGET_MAC},-55,-93,100,64," + ",".join([f"10.0:0.5" for _ in range(64)])
    # Non-target frame at seq=101 (interleaved)
    line2 = f"CSI_DATA,{AMBIENT_MAC},-60,-93,101,64," + ",".join([f"5.0:-0.2" for _ in range(64)])
    # Target frame at seq=104 (skipped seq 102 and 103: firmware gap of 2)
    line3 = f"CSI_DATA,{TARGET_MAC},-55,-93,104,64," + ",".join([f"10.0:0.5" for _ in range(64)])

    with PassiveEvidenceRecorder(output_dir=temp_evidence_dir, target_mac=TARGET_MAC) as rec:
        rec.process_line(line1)
        rec.process_line(line2)
        rec.process_line(line3)
        manifest = rec.finalize()

    # Firmware sequence jumps from 101 to 104 -> gap of 104 - 102 = 2
    assert manifest["sequence_reconciliation"]["firmware_sequence_gaps"] == 2
    # Target sequence jumps from 100 to 104 -> gap of 104 - 101 = 3 (includes intervening seq 101 + missing 102, 103)
    assert manifest["sequence_reconciliation"]["target_sequence_gaps"] == 3


def test_single_line_zero_duration_rate_safety(temp_evidence_dir):
    """Test 14: Rate calculation gracefully handles zero elapsed duration without ZeroDivisionError."""
    with PassiveEvidenceRecorder(output_dir=temp_evidence_dir, target_mac=TARGET_MAC) as rec:
        # Force identical monotonic timestamps
        rec.process_line(VALID_TARGET_LINE, host_monotonic=500.0, host_wall=1700000000.0)
        manifest = rec.finalize()

    assert manifest["timing"]["actual_duration_s"] == 0.0
    assert manifest["rates"]["target_rate_hz"] == 0.0
    assert manifest["rates"]["aggregate_rate_hz"] == 0.0

