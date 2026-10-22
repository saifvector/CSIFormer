"""
Real CSI Acquisition & Streaming Framework for CSIFormer Phase 14.

Capabilities:
- Hardware ESP32-S3 Serial Ingestion (auto-discovers COM ports with CH343, CP210x, FTDI, Espressif USB JTAG).
- Dual Telemetry Protocol Parser:
    Format A (Raw IQ stream):
        === CSI CALLBACK FIRED ===
        RSSI=-55 LEN=128 CSI:0,0,-17,-4,-17,-4,...
    Format B (Structured CSV stream):
        CSI_DATA,<mac>,<rssi>,<noise>,<seq>,<num_sc>,amp_0:phase_0,amp_1:phase_1,...
- Subcarrier Alignment: Uses ESP32CSIAdapter to interpolate/align to 56 HT20 subcarriers.
- Thread-Safe Sliding Temporal Window: Buffers incoming frames into [50, 56] tensors for continuous inference.
- Microsecond Timestamp Synchronization & Jitter Tracking.
- Packet Loss & Sequence Continuity Monitoring.
- Multi-Room (Bedroom, Office, Lab, Apartment) and Participant Metadata Storage.
- Clean Replay / Simulation Fallback for offline deterministic validation.
"""

import os
import sys
import time
import json
import csv
import math
import re
import threading
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Union
from collections import deque
import numpy as np

try:
    import serial
    import serial.tools.list_ports
    HAS_PYSERIAL = True
except ImportError:
    HAS_PYSERIAL = False

from app.services.esp32_csi_adapter import ESP32CSIAdapter
try:
    from app.services.session_validator import compute_session_sampling_rate
except ImportError:
    from backend.app.services.session_validator import compute_session_sampling_rate



class RealCSICollector:
    """
    Production-grade Real-Time ESP32-S3 CSI Acquisition Engine.
    Handles physical USB-UART serial streaming, packet parsing, window construction,
    and metadata logging for CSIFormer.
    """

    SUPPORTED_ROOMS = ["Bedroom", "Office", "Laboratory", "Apartment", "Benchmark-Chamber"]
    TARGET_SUBCARRIERS = 56
    WINDOW_SIZE = 50

    def __init__(
        self,
        port: Optional[str] = None,
        baud_rate: int = 115200,
        target_mode: str = "HT20",
        data_dir: str = "data/recordings",
        auto_connect: bool = False,
        target_mac: Optional[str] = "98:BA:5F:EF:28:26",
        filter_by_mac: bool = False
    ):
        self.port = port
        self.baud_rate = baud_rate
        self.target_mode = target_mode
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Configurable Target-Source Filtering (Phase 52)
        self.target_mac: Optional[str] = target_mac.upper() if target_mac else None
        self.filter_by_mac: bool = filter_by_mac
        self.filtered_non_target_packets: int = 0
        self.source_mac_counts: Dict[str, int] = {}

        self.adapter = ESP32CSIAdapter(target_mode=target_mode, target_rate_hz=30.0)

        # Thread-safe sliding temporal window: shape [50, 56]
        self._window_lock = threading.Lock()
        self.raw_frame_buffer = deque(maxlen=self.WINDOW_SIZE)
        self.phase_frame_buffer = deque(maxlen=self.WINDOW_SIZE)

        # Temporal and Sequence Metadata Buffers (Phase 56)
        self.timestamp_buffer = deque(maxlen=self.WINDOW_SIZE)
        self.monotonic_buffer = deque(maxlen=self.WINDOW_SIZE)
        self.sequence_buffer = deque(maxlen=self.WINDOW_SIZE)
        self.source_mac_buffer = deque(maxlen=self.WINDOW_SIZE)
        self.hw_timestamp_buffer = deque(maxlen=self.WINDOW_SIZE)

        # Connection & Threading state
        self.serial_handle: Optional[Any] = None
        self.is_connected = False
        self.is_streaming = False
        self._worker_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # Telemetry & Health Statistics
        self.packets_received = 0
        self.packets_lost = 0
        self.last_sequence: Optional[int] = None
        self.current_rssi: float = -60.0
        self.current_noise: float = -95.0
        self.packet_rate_hz: float = 0.0
        self.last_packet_time: float = time.time()
        self.jitter_ms: float = 0.0
        self.detected_protocol: str = "unknown"

        # Sequence Tracking & Loss Accounting Semantics (Phase 57 / 57.2 / 57.3)
        # Note: A gap in the firmware callback sequence counter proves that one or more
        # callback invocations occurred on ESP32 whose records were not parsed on the host.
        # It does NOT prove the loss occurred specifically in the UART transport layer;
        # it could stem from firmware queue drops, UART TX/RX drops, parser rejections, or host OS buffering.
        self.last_firmware_seq: Optional[int] = None
        # Primary authoritative metric: callback sequence counter gaps observed across parsed records
        self.firmware_sequence_gaps: int = 0
        self.target_sequence_gaps: int = 0
        self.counter_resets: int = 0
        self.out_of_order_packets: int = 0
        self.duplicate_packets: int = 0
        # Backward-compatible legacy aliases: mirror firmware_sequence_gaps.
        # WARNING: These legacy aliases do NOT independently prove UART or transport-layer drops;
        # attributing callback counter gaps to the serial wire without a hardware logic analyzer is an overclaim.
        self.confirmed_transport_loss: int = 0
        self.packets_lost: int = 0

        # Diagnostic State Machine & Telemetry (Phase 21)
        self.diagnostic_state: str = "SERIAL_DISCONNECTED"
        self.total_bytes_received: int = 0
        self.total_lines_received: int = 0
        self.total_records_detected: int = 0
        self.csi_packets_parsed: int = 0
        self.parse_errors: int = 0
        self.boot_messages: List[str] = []
        self.last_valid_packet_time: Optional[float] = None
        self.raw_csi_dimensions: Optional[int] = None
        self.termination_reason: Optional[str] = None

        # Recording Session Metadata
        self.is_recording = False
        self.current_session_id: Optional[str] = None
        self.session_metadata: Dict[str, Any] = {}
        self.recorded_frames: List[Dict[str, Any]] = []

        if auto_connect:
            self.connect()

    def discover_esp32_port(self) -> Optional[str]:
        """
        Scans system for connected ESP32 / USB-UART bridge devices.
        Known VIDs: 0x1A86 (WCH CH343/CH340), 0x10C4 (CP210x), 0x303A (Espressif Native USB), 0x0403 (FTDI).
        """
        if not HAS_PYSERIAL:
            return None

        ports = list(serial.tools.list_ports.comports())
        # Priority 1: Match known ESP32 / CH343 / CP210x Vendor IDs
        for p in ports:
            if p.vid in [0x1A86, 0x10C4, 0x303A, 0x0403]:
                return p.device

        # Priority 2: Match friendly name
        for p in ports:
            desc = (p.description or "").lower()
            if any(k in desc for k in ["ch343", "ch340", "cp210", "uart", "espressif", "jtag"]):
                return p.device

        # Priority 3: Fall back to first available non-Bluetooth port
        for p in ports:
            if "bluetooth" not in (p.description or "").lower():
                return p.device

        return None

    def connect(self, port: Optional[str] = None, baud_rate: Optional[int] = None) -> bool:
        """Establishes non-blocking connection to the ESP32-S3 serial interface."""
        if not HAS_PYSERIAL:
            print("[RealCSICollector] Warning: pyserial is not installed.")
            self.diagnostic_state = "SERIAL_DISCONNECTED"
            self.termination_reason = "pyserial_not_installed"
            return False

        target_port = port or self.port or self.discover_esp32_port()
        target_baud = baud_rate or self.baud_rate

        if not target_port:
            print("[RealCSICollector] No ESP32-S3 serial port detected.")
            self.diagnostic_state = "SERIAL_DISCONNECTED"
            self.termination_reason = "no_port_detected"
            return False

        try:
            if self.serial_handle and self.serial_handle.is_open:
                self.serial_handle.close()

            self.serial_handle = serial.Serial()
            self.serial_handle.port = target_port
            self.serial_handle.baudrate = target_baud
            self.serial_handle.timeout = 1.0
            self.serial_handle.write_timeout = 1.0
            # Prevent DTR/RTS auto-reset into bootloader (CH343/ESP32-S3 auto-download trap)
            self.serial_handle.dtr = False
            self.serial_handle.rts = False
            self.serial_handle.open()

            self.port = target_port
            self.baud_rate = target_baud
            self.is_connected = True
            self.diagnostic_state = "SERIAL_CONNECTED_IDLE"
            self.termination_reason = None
            print(f"[RealCSICollector] Successfully connected to {self.port} @ {self.baud_rate} baud.")
            return True
        except Exception as e:
            print(f"[RealCSICollector] Connection failed on {target_port}: {e}")
            self.is_connected = False
            self.diagnostic_state = "SERIAL_DISCONNECTED"
            self.termination_reason = f"connection_failed: {e}"
            return False

    def trigger_normal_reset(self) -> bool:
        """
        Pulses RTS (EN) low while keeping DTR (GPIO0) high (inactive)
        to trigger a clean SPI fast flash boot on ESP32-S3, escaping ROM download mode.
        """
        if not self.serial_handle or not getattr(self.serial_handle, "is_open", False):
            return False
        try:
            self.serial_handle.dtr = False
            self.serial_handle.rts = True
            time.sleep(0.05)
            self.serial_handle.rts = False
            time.sleep(0.1)
            return True
        except Exception as e:
            print(f"[RealCSICollector] Reset pulse error: {e}")
            return False

    def is_port_released(self) -> bool:
        """
        Confirms whether the serial port and background acquisition thread
        are cleanly and completely released.
        """
        thread_stopped = (self._worker_thread is None) or (not self._worker_thread.is_alive())
        serial_closed = (self.serial_handle is None) or (not getattr(self.serial_handle, "is_open", False))
        return bool(thread_stopped and serial_closed and not self.is_connected and not self.is_streaming)

    def disconnect(self) -> bool:
        """Safely stops streaming, closes the serial port, and verifies port release (idempotent)."""
        self.stop_streaming()
        if self.serial_handle:
            try:
                if getattr(self.serial_handle, "is_open", False):
                    self.serial_handle.close()
            except Exception as e:
                print(f"[RealCSICollector] Error closing serial port: {e}")
            finally:
                if hasattr(self.serial_handle, "is_open"):
                    try:
                        self.serial_handle.is_open = False
                    except Exception:
                        pass
        self.is_connected = False
        self.diagnostic_state = "SERIAL_DISCONNECTED"
        released = self.is_port_released()
        print(f"[RealCSICollector] Disconnected serial interface. Port released: {released}")
        return released

    def start_streaming(self):
        """Starts background worker thread to ingest and process CSI packets."""
        if self.is_streaming:
            return

        if not self.is_connected:
            if not self.connect():
                print("[RealCSICollector] Cannot start streaming: hardware not connected.")
                return

        self._stop_event.clear()
        self.is_streaming = True
        self._worker_thread = threading.Thread(target=self._serial_ingest_loop, daemon=True)
        self._worker_thread.start()
        print("[RealCSICollector] Background CSI acquisition loop started.")

    def stop_streaming(self):
        """Signals the background acquisition thread to terminate (idempotent)."""
        self.is_streaming = False
        self._stop_event.set()
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=2.0)
        self._worker_thread = None

    def _serial_ingest_loop(self):
        """Continuous background serial reading and parsing worker."""
        line_buffer = ""
        while not self._stop_event.is_set():
            try:
                if not self.serial_handle or not getattr(self.serial_handle, "is_open", False):
                    time.sleep(0.2)
                    continue

                in_w = getattr(self.serial_handle, "in_waiting", 0) or 1
                raw_bytes = self.serial_handle.read(in_w)
                if not raw_bytes:
                    continue

                self.total_bytes_received += len(raw_bytes)
                text = raw_bytes.decode("ascii", errors="ignore")
                line_buffer += text

                while "\n" in line_buffer:
                    line, line_buffer = line_buffer.split("\n", 1)
                    line = line.strip()
                    if line:
                        self.total_lines_received += 1
                        # Capture boot messages or diagnostic logs
                        if any(kw in line for kw in ["rst:", "boot:", "configsip:", "clk_drv:", "spi_fast_flash", "wifi:", "CSI callback", "CSI Receiver", "Haven't to connect", "connecting to", "MAC", "channel"]):
                            if len(self.boot_messages) < 100:
                                self.boot_messages.append(line)

                        is_candidate = ("RSSI=" in line and "CSI:" in line) or line.startswith("CSI_DATA")
                        if is_candidate:
                            self.total_records_detected += 1
                            parsed = self.parse_raw_telemetry_line(line)
                            if parsed:
                                raw_amps = parsed.get("raw_amplitudes", [])
                                if len(raw_amps) > 0:
                                    self._process_parsed_frame(parsed)
                                else:
                                    self.parse_errors += 1
                            else:
                                self.parse_errors += 1
                                if self.csi_packets_parsed == 0:
                                    self.diagnostic_state = "RECORDS_RECEIVED_PARSE_FAILED"
                        else:
                            if self.csi_packets_parsed == 0 and self.total_records_detected == 0:
                                self.diagnostic_state = "SERIAL_BYTES_NO_VALID_RECORDS"

            except (serial.SerialException, OSError) as e:
                print(f"[RealCSICollector] Serial stream error: {e}.")
                self.is_connected = False
                self.diagnostic_state = "SERIAL_DISCONNECTED"
                self.termination_reason = f"serial_error: {e}"
                if self._stop_event.is_set():
                    break
                time.sleep(0.5)
                if not self._stop_event.is_set():
                    self.connect()

    def parse_raw_telemetry_line(self, line: str) -> Optional[Dict[str, Any]]:
        """
        Parses raw CSI strings into standardized packet frames.
        Supports both the running firmware (Format A) and structured repository firmware (Format B).
        """
        line = line.strip()
        if not line:
            return None

        # Format A: RSSI=-55 LEN=128 CSI:0,0,-17,-4,... or RSSI=-59 LEN=256 CSI:0,0,...
        if "RSSI=" in line and ("CSI:" in line or "CSI=" in line):
            try:
                self.detected_protocol = "raw_iq_stream"
                rssi_m = re.search(r"RSSI=([-+]?\d+(?:\.\d+)?)", line)
                rssi = float(rssi_m.group(1)) if rssi_m else -60.0

                len_m = re.search(r"LEN=(\d+)", line)
                payload_len = int(len_m.group(1)) if len_m else 128

                csi_idx = line.find("CSI:")
                if csi_idx == -1:
                    csi_idx = line.find("CSI=")
                if csi_idx == -1:
                    return None

                iq_str = line[csi_idx + 4:].strip().strip("[]").strip()
                nums = [int(v) for v in re.findall(r"[-+]?\d+", iq_str)]
                if len(nums) < 2:
                    return None

                # IQ interleaved pairs
                amps = []
                phases = []
                for i in range(0, len(nums) - 1, 2):
                    r = nums[i]
                    im = nums[i + 1]
                    amps.append(math.sqrt(r * r + im * im))
                    phases.append(math.atan2(im, r))

                return {
                    "timestamp": time.time(),
                    "host_monotonic_time": time.perf_counter(),
                    "sequence": self.packets_received + 1,
                    "mac": "ESP32-S3-NODE-01",
                    "rssi": rssi,
                    "noise_floor": -95.0,
                    "num_subcarriers": len(amps),
                    "raw_amplitudes": amps,
                    "raw_phases": phases
                }
            except Exception:
                return None

        # Format B v2 (Extended Structured CSV with ESP-IDF Hardware Microsecond Timestamps & 802.11 MAC Sequence):
        # CSI_DATA_V2,<mac>,<rssi>,<noise>,<seq>,<hw_timestamp_us>,<rx_seq>,<num_sc>,amp_0:phase_0,...
        if line.startswith("CSI_DATA_V2"):
            try:
                self.detected_protocol = "structured_csi_data_v2"
                content = line.strip()
                tokens = content.split(",")
                if len(tokens) < 8:
                    return None

                mac = tokens[1]
                rssi = float(tokens[2])
                noise = float(tokens[3])
                seq = int(tokens[4])
                hw_ts_us = int(tokens[5])
                rx_seq = int(tokens[6])
                num_sc = int(tokens[7])

                remainder = ",".join(tokens[8:]).replace("[", "").replace("]", "")
                subcarrier_tokens = [t.strip() for t in re.split(r"[,;]", remainder) if t.strip()]

                amps = []
                phases = []
                for pair in subcarrier_tokens:
                    if ":" in pair:
                        a, p = pair.split(":", 1)
                        amps.append(float(a))
                        phases.append(float(p))

                if len(amps) == 0:
                    return None

                return {
                    "timestamp": time.time(),
                    "host_monotonic_time": time.perf_counter(),
                    "hw_timestamp_us": hw_ts_us,
                    "rx_seq": rx_seq,
                    "sequence": seq,
                    "mac": mac,
                    "rssi": rssi,
                    "noise_floor": noise,
                    "num_subcarriers": len(amps),
                    "raw_amplitudes": amps,
                    "raw_phases": phases
                }
            except Exception:
                return None

        # Format B (Historical Structured CSV stream):
        # CSI_DATA,<mac>,<rssi>,<noise>,<seq>,<num_sc>,amp_0:phase_0,...
        elif line.startswith("CSI_DATA"):
            try:
                self.detected_protocol = "structured_csi_data"
                content = line.strip()
                tokens = content.split(",")
                if len(tokens) < 6:
                    return None

                mac = tokens[1]
                rssi = float(tokens[2])
                noise = float(tokens[3])
                seq = int(tokens[4])
                num_sc = int(tokens[5])

                remainder = ",".join(tokens[6:]).replace("[", "").replace("]", "")
                subcarrier_tokens = [t.strip() for t in re.split(r"[,;]", remainder) if t.strip()]

                amps = []
                phases = []
                for pair in subcarrier_tokens:
                    if ":" in pair:
                        a, p = pair.split(":", 1)
                        amps.append(float(a))
                        phases.append(float(p))

                if len(amps) == 0:
                    return None

                return {
                    "timestamp": time.time(),
                    "host_monotonic_time": time.perf_counter(),
                    "sequence": seq,
                    "mac": mac,
                    "rssi": rssi,
                    "noise_floor": noise,
                    "num_subcarriers": len(amps),
                    "raw_amplitudes": amps,
                    "raw_phases": phases
                }
            except Exception:
                return None

        return None

    def _process_parsed_frame(self, frame: Dict[str, Any]):
        """Processes a validated frame: aligns subcarriers to 56 HT20 and updates window buffer."""
        # 1. Firmware Sequence Tracking (evaluated across all physical arrivals before filtering)
        seq = frame.get("sequence")
        if seq is not None:
            if self.last_firmware_seq is not None:
                if seq > self.last_firmware_seq:
                    f_gap = seq - (self.last_firmware_seq + 1)
                    if f_gap > 0:
                        self.firmware_sequence_gaps += f_gap
                        self.confirmed_transport_loss = self.firmware_sequence_gaps
                        self.packets_lost = self.firmware_sequence_gaps
                    self.last_firmware_seq = seq
                elif seq < self.last_firmware_seq:
                    # 32-bit unsigned wraparound check (e.g. 0xFFFFFFFF -> 0)
                    if self.last_firmware_seq > 0xFFFF0000 and seq < 0x10000:
                        f_gap = (seq + 0x100000000) - (self.last_firmware_seq + 1)
                        if f_gap > 0:
                            self.firmware_sequence_gaps += f_gap
                            self.confirmed_transport_loss = self.firmware_sequence_gaps
                            self.packets_lost = self.firmware_sequence_gaps
                        self.last_firmware_seq = seq
                    elif (self.last_firmware_seq - seq) > 1000 or (self.last_firmware_seq >= 100 and seq <= 10):
                        # Genuine firmware reboot / counter restart
                        self.counter_resets += 1
                        self.last_firmware_seq = seq
                    else:
                        # Out-of-order packet arrival (jitter) without regressing high-water sequence
                        self.out_of_order_packets += 1
                else:
                    # Duplicate sequence number (seq == last_firmware_seq)
                    self.duplicate_packets += 1
                    if self.detected_protocol != "raw_iq_stream":
                        return
            else:
                self.last_firmware_seq = seq

        # 2. Source MAC tracking & Target-Source Filtering (Phase 52)
        source_mac = frame.get("mac", "")
        if source_mac:
            source_mac_norm = source_mac.upper()
            self.source_mac_counts[source_mac_norm] = self.source_mac_counts.get(source_mac_norm, 0) + 1
        else:
            source_mac_norm = ""

        if self.filter_by_mac:
            # Fail closed if required metadata is missing
            if not source_mac_norm or not self.target_mac:
                self.parse_errors += 1
                return
            if source_mac_norm != self.target_mac:
                self.filtered_non_target_packets += 1
                return

        now = frame["timestamp"]
        dt = max(0.001, now - self.last_packet_time)
        self.last_packet_time = now
        self.last_valid_packet_time = now

        # Update metrics
        self.packets_received += 1
        self.csi_packets_parsed += 1
        self.diagnostic_state = "CSI_STREAM_ACTIVE"
        self.current_rssi = frame["rssi"]
        self.current_noise = frame["noise_floor"]
        self.packet_rate_hz = round(0.9 * self.packet_rate_hz + 0.1 * (1.0 / dt), 1)

        # 3. Target sequence gap tracking & loss reconciliation
        if seq is not None:
            if self.last_sequence is not None:
                if seq > self.last_sequence:
                    t_gap = seq - (self.last_sequence + 1)
                    if t_gap > 0:
                        self.target_sequence_gaps += t_gap
                elif seq < self.last_sequence:
                    if self.last_sequence > 0xFFFF0000 and seq < 0x10000:
                        t_gap = (seq + 0x100000000) - (self.last_sequence + 1)
                        if t_gap > 0:
                            self.target_sequence_gaps += t_gap
            self.last_sequence = seq

        # packets_lost and confirmed_transport_loss mirror observed firmware sequence gaps
        # (loss layer cannot be isolated to transport alone without physical bus analysis)
        self.confirmed_transport_loss = self.firmware_sequence_gaps
        self.packets_lost = self.firmware_sequence_gaps

        # Align subcarriers to standardized TARGET_SUBCARRIERS (56)
        raw_amps = np.array(frame["raw_amplitudes"], dtype=np.float32)
        raw_phases = np.array(frame["raw_phases"], dtype=np.float32)

        if len(raw_amps) == 0:
            return

        self.raw_csi_dimensions = len(raw_amps)

        if len(raw_amps) != self.TARGET_SUBCARRIERS:
            # Resample or interpolate to exactly 56 subcarriers
            x_old = np.linspace(0, 1, len(raw_amps))
            x_new = np.linspace(0, 1, self.TARGET_SUBCARRIERS)
            aligned_amp = np.interp(x_new, x_old, raw_amps).astype(np.float32)
            aligned_phase = np.interp(x_new, x_old, raw_phases).astype(np.float32)
        else:
            aligned_amp = raw_amps
            aligned_phase = raw_phases

        with self._window_lock:
            self.raw_frame_buffer.append(aligned_amp)
            self.phase_frame_buffer.append(aligned_phase)
            self.timestamp_buffer.append(now)
            self.monotonic_buffer.append(frame.get("host_monotonic_time", now))
            self.sequence_buffer.append(seq)
            self.source_mac_buffer.append(source_mac)
            self.hw_timestamp_buffer.append(frame.get("hw_timestamp_us"))

        # Recording handling
        if self.is_recording:
            rec_frame = {
                "timestamp": now,
                "host_monotonic_time": frame.get("host_monotonic_time", now),
                "sequence": seq,
                "mac": source_mac,
                "rssi": frame["rssi"],
                "noise": frame["noise_floor"],
                "raw_amplitudes": raw_amps.tolist(),
                "raw_phases": raw_phases.tolist(),
                "raw_num_subcarriers": len(raw_amps),
                "amplitudes": aligned_amp.tolist(),
                "phases": aligned_phase.tolist(),
                "num_subcarriers": len(aligned_amp)
            }
            if "hw_timestamp_us" in frame:
                rec_frame["hw_timestamp_us"] = frame["hw_timestamp_us"]
            if "rx_seq" in frame:
                rec_frame["rx_seq"] = frame["rx_seq"]

            if len(raw_amps) == 64:
                comp = self.adapter.separate_physical_and_null_components(raw_amps)
                rec_frame["physical_active_amplitudes"] = comp["active_52"].tolist()
                rec_frame["physical_null_amplitudes"] = comp["null_12"].tolist()
                rec_frame["physical_active_subcarrier_count"] = 52
                rec_frame["physical_null_subcarrier_count"] = 12
            self.recorded_frames.append(rec_frame)

    def get_stream_diagnostics(self) -> Dict[str, Any]:
        """
        Returns bounded, non-persistent diagnostic telemetry for stream health,
        source MAC counts, sequence continuity, packet rates, and parser errors.
        """
        return {
            "diagnostic_state": self.diagnostic_state,
            "is_connected": self.is_connected,
            "is_streaming": self.is_streaming,
            "port": self.port,
            "baud_rate": self.baud_rate,
            "target_mac": self.target_mac,
            "filter_by_mac": self.filter_by_mac,
            "packets_received": self.packets_received,
            "packets_lost": self.packets_lost,
            "confirmed_transport_loss": self.confirmed_transport_loss,
            "firmware_sequence_gaps": self.firmware_sequence_gaps,
            "target_sequence_gaps": self.target_sequence_gaps,
            "counter_resets": self.counter_resets,
            "out_of_order_packets": self.out_of_order_packets,
            "duplicate_packets": self.duplicate_packets,
            "csi_packets_parsed": self.csi_packets_parsed,
            "parse_errors": self.parse_errors,
            "filtered_non_target_packets": self.filtered_non_target_packets,
            "source_mac_counts": dict(self.source_mac_counts),
            "packet_rate_hz": self.packet_rate_hz,
            "current_rssi": self.current_rssi,
            "current_noise": self.current_noise,
            "raw_csi_dimensions": self.raw_csi_dimensions,
            "port_released": self.is_port_released(),
        }

    def get_latest_window(
        self,
        return_metadata: bool = False
    ) -> Optional[Union[Tuple[np.ndarray, np.ndarray], Tuple[np.ndarray, np.ndarray, Dict[str, Any]]]]:
        """
        Retrieves the latest complete temporal window [50, 56] for CSIFormer inference.

        Args:
            return_metadata: If True, returns a 3-tuple (raw_win, phase_win, metadata_dict)
                             containing temporal metadata (timestamps, monotonic times,
                             empirical rate, interval stats, sequence numbers).
                             If False (default), returns standard 2-tuple (raw_win, phase_win)
                             for strict backward compatibility with existing consumers.

        Returns:
            Tuple of (raw_win, phase_win) if buffer is full and return_metadata is False;
            Tuple of (raw_win, phase_win, meta_dict) if return_metadata is True;
            else None.
        """
        with self._window_lock:
            if len(self.raw_frame_buffer) < self.WINDOW_SIZE:
                return None
            raw_win = np.stack(list(self.raw_frame_buffer), axis=0)
            phase_win = np.stack(list(self.phase_frame_buffer), axis=0)
            if not return_metadata:
                return raw_win, phase_win

            monotonic_arr = np.array(list(self.monotonic_buffer), dtype=np.float64)
            wall_arr = np.array(list(self.timestamp_buffer), dtype=np.float64)
            seq_list = list(self.sequence_buffer)
            diffs_m = np.diff(monotonic_arr) if len(monotonic_arr) > 1 else np.array([])
            span_m = float(monotonic_arr[-1] - monotonic_arr[0]) if len(monotonic_arr) > 1 else 0.0
            empirical_rate = (len(monotonic_arr) - 1) / span_m if span_m > 0 else 0.0

            has_hw = (len(self.hw_timestamp_buffer) == len(monotonic_arr)) and all(x is not None for x in self.hw_timestamp_buffer)
            meta_dict = {
                "timestamps": wall_arr,
                "monotonic_timestamps": monotonic_arr,
                "sequences": seq_list,
                "source_macs": list(self.source_mac_buffer),
                "span_seconds": round(span_m, 6),
                "empirical_rate_hz": round(empirical_rate, 2),
                "mean_interval_ms": round(float(np.mean(diffs_m) * 1000.0), 3) if len(diffs_m) > 0 else 0.0,
                "max_interval_ms": round(float(np.max(diffs_m) * 1000.0), 3) if len(diffs_m) > 0 else 0.0,
                "min_interval_ms": round(float(np.min(diffs_m) * 1000.0), 3) if len(diffs_m) > 0 else 0.0,
                "std_interval_ms": round(float(np.std(diffs_m) * 1000.0), 3) if len(diffs_m) > 0 else 0.0,
                "has_hw_timestamps": has_hw,
                "hw_timestamps_us": list(self.hw_timestamp_buffer) if has_hw else None,
            }
            return raw_win, phase_win, meta_dict

    def get_window_timing_diagnostics(self) -> Dict[str, Any]:
        """
        Returns timing and arrival rate telemetry for the frames currently in the buffer,
        even if the buffer has not yet reached WINDOW_SIZE.
        """
        with self._window_lock:
            n = len(self.monotonic_buffer)
            if n < 2:
                return {
                    "buffered_frames": n,
                    "span_seconds": 0.0,
                    "empirical_rate_hz": 0.0,
                    "mean_interval_ms": 0.0,
                    "std_interval_ms": 0.0,
                    "cv_interval": 0.0,
                    "is_full": n >= self.WINDOW_SIZE,
                }
            mono = np.array(list(self.monotonic_buffer), dtype=np.float64)
            diffs = np.diff(mono)
            span = float(mono[-1] - mono[0])
            rate = (n - 1) / span if span > 0 else 0.0
            mean_dt = float(np.mean(diffs))
            std_dt = float(np.std(diffs))
            cv = (std_dt / mean_dt) if mean_dt > 0 else 0.0

            return {
                "buffered_frames": n,
                "span_seconds": round(span, 6),
                "empirical_rate_hz": round(rate, 2),
                "mean_interval_ms": round(mean_dt * 1000.0, 3),
                "std_interval_ms": round(std_dt * 1000.0, 3),
                "cv_interval": round(cv, 4),
                "min_interval_ms": round(float(np.min(diffs) * 1000.0), 3),
                "max_interval_ms": round(float(np.max(diffs) * 1000.0), 3),
                "is_full": n >= self.WINDOW_SIZE,
                "has_hw_timestamps": (len(self.hw_timestamp_buffer) == n) and all(x is not None for x in self.hw_timestamp_buffer),
            }

    def get_diagnostic_state(self) -> str:
        """Computes current real-time diagnostic state based on hardware and packet stream telemetry."""
        if not self.is_connected or not self.serial_handle:
            self.diagnostic_state = "SERIAL_DISCONNECTED"
            return self.diagnostic_state

        is_open = getattr(self.serial_handle, "is_open", False)
        if not is_open:
            self.diagnostic_state = "SERIAL_DISCONNECTED"
            return self.diagnostic_state

        now = time.time()
        if self.csi_packets_parsed > 0:
            if self.last_valid_packet_time and (now - self.last_valid_packet_time > 2.0):
                self.diagnostic_state = "STREAM_INTERRUPTED"
            else:
                self.diagnostic_state = "CSI_STREAM_ACTIVE"
        elif self.parse_errors > 0 or (self.total_records_detected > 0 and self.csi_packets_parsed == 0):
            self.diagnostic_state = "RECORDS_RECEIVED_PARSE_FAILED"
        elif self.total_bytes_received > 0 or self.total_lines_received > 0:
            self.diagnostic_state = "SERIAL_BYTES_NO_VALID_RECORDS"
        else:
            self.diagnostic_state = "SERIAL_CONNECTED_IDLE"

        return self.diagnostic_state

    def get_stream_health(self) -> Dict[str, Any]:
        """Returns comprehensive real-time streaming health telemetry."""
        total_delivered = self.packets_received + self.filtered_non_target_packets
        total_expected = total_delivered + self.firmware_sequence_gaps
        loss_pct = round((self.firmware_sequence_gaps / total_expected * 100), 2) if total_expected > 0 else 0.0
        state = self.get_diagnostic_state()

        return {
            "is_connected": self.is_connected,
            "is_streaming": self.is_streaming,
            "diagnostic_state": state,
            "port": self.port or "DISCONNECTED",
            "baud_rate": self.baud_rate,
            "detected_protocol": self.detected_protocol,
            "total_bytes_received": self.total_bytes_received,
            "total_lines_received": self.total_lines_received,
            "total_records_detected": self.total_records_detected,
            "csi_packets_parsed": self.csi_packets_parsed,
            "parse_errors": self.parse_errors,
            "filtered_non_target_packets": self.filtered_non_target_packets,
            "raw_csi_dimensions": self.raw_csi_dimensions,
            "packets_received": self.packets_received,
            "packets_lost": self.packets_lost,
            "confirmed_transport_loss": self.confirmed_transport_loss,
            "firmware_sequence_gaps": self.firmware_sequence_gaps,
            "target_sequence_gaps": self.target_sequence_gaps,
            "counter_resets": self.counter_resets,
            "out_of_order_packets": self.out_of_order_packets,
            "duplicate_packets": self.duplicate_packets,
            "packet_loss_pct": loss_pct,
            "packet_rate_hz": self.packet_rate_hz,
            "rssi_dbm": self.current_rssi,
            "noise_floor_dbm": self.current_noise,
            "snr_db": round(self.current_rssi - self.current_noise, 1),
            "buffer_fill_pct": round(len(self.raw_frame_buffer) / self.WINDOW_SIZE * 100, 1),
            "window_ready": len(self.raw_frame_buffer) >= self.WINDOW_SIZE,
            "last_valid_packet_time": self.last_valid_packet_time,
            "boot_messages": self.boot_messages[-10:],
            "termination_reason": self.termination_reason
        }

    def parse_raw_line(self, line: str) -> Optional[Dict[str, Any]]:
        """Convenience alias for parse_raw_telemetry_line."""
        return self.parse_raw_telemetry_line(line)

    def get_stats(self) -> Dict[str, Any]:
        """Convenience alias for get_stream_health."""
        return self.get_stream_health()

    def _buffer_packet(self, frame: Optional[Dict[str, Any]]):
        """Convenience helper to buffer a single validated packet frame."""
        if frame:
            self._process_parsed_frame(frame)

    # =========================================================================
    # Multi-Room Session Recording & Metadata Logging
    # =========================================================================
    def start_session_recording(
        self,
        session_name: str,
        room_type: str = "Bedroom",
        participant_id: str = "User-01",
        activity_label: str = "walk",
        room_dimensions_m: Tuple[float, float, float] = (4.0, 3.5, 2.8),
        tx_rx_distance_m: float = 2.5,
        nlos: bool = False,
        orientation: str = "LOS_Facing_TxRx",
        ground_truth_confirmed: bool = True,
        notes: str = ""
    ) -> Dict[str, Any]:
        """Initiates a labeled multi-room recording session with full environmental metadata."""
        if room_type not in self.SUPPORTED_ROOMS:
            room_type = "Office"

        # Mark as unknown if not confirmed
        actual_label = activity_label if ground_truth_confirmed else "unknown"

        self.is_recording = True
        self.recorded_frames = []
        self._last_saved_session_result = None
        clean_name = session_name.replace(" ", "_")
        self.current_session_id = f"phase16_{clean_name}_{int(time.time())}"
        self._rec_start_lost = self.packets_lost
        self._rec_start_fw_gaps = self.firmware_sequence_gaps
        self._rec_start_received = self.packets_received
        self._rec_start_time = time.time()

        self.session_metadata = {
            "session_id": self.current_session_id,
            "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "room_type": room_type,
            "room_dimensions_xyz_meters": list(room_dimensions_m),
            "tx_rx_distance_meters": tx_rx_distance_m,
            "orientation": orientation,
            "nlos_obstruction": nlos,
            "participant_id": participant_id,
            "ground_truth_activity": actual_label,
            "ground_truth_confirmed": ground_truth_confirmed,
            "notes": notes,
            "hardware": {
                "board": "ESP32-S3 (Xtensa LX7)",
                "chip_revision": "v0.2",
                "uart_bridge": "CH343",
                "port": self.port or "COM5",
                "baud_rate": self.baud_rate,
                "protocol": self.detected_protocol
            },
            "rf_config": {
                "channel": 7,
                "frequency_ghz": 2.442,
                "bandwidth_mode": self.target_mode,
                "subcarriers": self.TARGET_SUBCARRIERS
            }
        }

        return {
            "status": "recording_started",
            "session_id": self.current_session_id,
            "room_type": room_type,
            "participant": participant_id,
            "activity": actual_label
        }

    def stop_session_recording(self) -> Dict[str, Any]:
        """Stops recording and persists JSON and CSV artifacts to disk with atomic write."""
        if not self.is_recording:
            if hasattr(self, "_last_saved_session_result") and self._last_saved_session_result:
                return self._last_saved_session_result
            return {"status": "not_recording"}

        self.is_recording = False
        frame_count = len(self.recorded_frames)
        session_id = self.current_session_id or f"session_{int(time.time())}"
        dur_s = max(0.001, time.time() - getattr(self, "_rec_start_time", time.time()))
        pkts_lost = max(0, self.packets_lost - getattr(self, "_rec_start_lost", 0))
        fw_gaps = max(0, self.firmware_sequence_gaps - getattr(self, "_rec_start_fw_gaps", 0))

        # Compute standardized sampling rate metrics
        timestamps = [f["timestamp"] for f in self.recorded_frames if "timestamp" in f]
        rate_stats = compute_session_sampling_rate(timestamps, wall_duration_s=dur_s)

        # Update metadata with packet health and actual duration
        self.session_metadata["duration_seconds"] = round(dur_s, 2)
        self.session_metadata["timestamp_span_seconds"] = round(rate_stats["timestamp_span_s"], 4)
        self.session_metadata["packets_received"] = frame_count
        self.session_metadata["firmware_sequence_gaps"] = fw_gaps
        self.session_metadata["packets_lost"] = pkts_lost  # legacy alias
        self.session_metadata["confirmed_transport_loss"] = fw_gaps  # legacy alias
        self.session_metadata["loss_rate"] = round(fw_gaps / max(1, frame_count + fw_gaps), 4)
        self.session_metadata["mean_sampling_rate_hz"] = (
            round(rate_stats["empirical_sampling_rate_hz"], 2)
            if rate_stats["valid"]
            else round(frame_count / dur_s, 2)
        )
        self.session_metadata["wall_clock_rate_hz"] = round(frame_count / dur_s, 2)

        # 1. Prevent accidental overwriting of previously collected sessions
        base_id = session_id
        counter = 1
        json_path = self.data_dir / f"{session_id}.json"
        while json_path.exists():
            session_id = f"{base_id}_v{counter}"
            json_path = self.data_dir / f"{session_id}.json"
            counter += 1
        self.session_metadata["session_id"] = session_id

        full_payload = {
            "metadata": self.session_metadata,
            "frame_count": frame_count,
            "frames": self.recorded_frames
        }

        # Atomic JSON persistence
        tmp_json = self.data_dir / f"{session_id}.json.tmp"
        try:
            with open(tmp_json, "w", encoding="utf-8") as f:
                json.dump(full_payload, f, indent=2)
                f.flush()
                try:
                    os.fsync(f.fileno())
                except OSError:
                    pass
            os.replace(tmp_json, json_path)
        except Exception as e:
            if tmp_json.exists():
                try:
                    tmp_json.unlink()
                except OSError:
                    pass
            print(f"[RealCSICollector] JSON write error for {session_id}: {e}")
            res = {
                "status": "error",
                "error": f"JSON write failed: {e}",
                "session_id": session_id,
                "frame_count": frame_count
            }
            self._last_saved_session_result = res
            return res

        # Atomic CSV summary persistence
        csv_path = self.data_dir / f"{session_id}.csv"
        tmp_csv = self.data_dir / f"{session_id}.csv.tmp"
        try:
            with open(tmp_csv, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                header = ["timestamp", "sequence", "rssi", "noise"]
                header += [f"amp_{i}" for i in range(self.TARGET_SUBCARRIERS)]
                writer.writerow(header)
                for rf in self.recorded_frames:
                    row = [rf["timestamp"], rf["sequence"], rf["rssi"], rf["noise"]]
                    row.extend(rf.get("amplitudes", []))
                    writer.writerow(row)
                f.flush()
                try:
                    os.fsync(f.fileno())
                except OSError:
                    pass
            os.replace(tmp_csv, csv_path)
        except Exception as e:
            if tmp_csv.exists():
                try:
                    tmp_csv.unlink()
                except OSError:
                    pass
            print(f"[RealCSICollector] CSV write error for {session_id}: {e}")
            res = {
                "status": "error",
                "error": f"CSV write failed: {e}",
                "session_id": session_id,
                "frame_count": frame_count,
                "json_path": str(json_path)
            }
            self._last_saved_session_result = res
            return res

        print(f"[RealCSICollector] Saved recording session: {json_path} ({frame_count} frames)")
        res = {
            "status": "recording_saved",
            "session_id": session_id,
            "frame_count": frame_count,
            "json_path": str(json_path),
            "csv_path": str(csv_path)
        }
        self._last_saved_session_result = res
        return res

    # =========================================================================
    # High-Fidelity Simulation & Recorded Replay Pathway
    # =========================================================================
    def inject_synthetic_burst(
        self,
        activity: str = "walk",
        num_frames: int = 50,
        carrier_rssi: float = -55.0,
        noise_level: float = 0.5
    ):
        """
        Injects a synthetic 50-frame burst into the temporal window for deterministic unit testing.
        Preserves RF kinematic physics across subcarriers.
        """
        t = np.linspace(0, 1.66, num_frames)  # ~30 Hz for 1.66 seconds
        subcarrier_idx = np.arange(self.TARGET_SUBCARRIERS)

        # Activity-dependent kinematic signatures
        if activity in ["walk", "run"]:
            doppler_freq = 15.0 if activity == "run" else 7.5
            kinematic_amp = 8.0 if activity == "run" else 4.0
        elif activity == "fall":
            doppler_freq = 20.0
            kinematic_amp = 18.0
        else:
            doppler_freq = 2.0
            kinematic_amp = 1.5

        for i, ti in enumerate(t):
            # Static torso multipath base
            base_curve = 15.0 + 3.0 * np.sin(subcarrier_idx * 0.15)
            # Dynamic kinematic perturbation
            perturb = kinematic_amp * np.sin(2 * np.pi * doppler_freq * ti + subcarrier_idx * 0.1)
            noise = np.random.normal(0, noise_level, self.TARGET_SUBCARRIERS)
            amps = np.clip(base_curve + perturb + noise, 0.1, 50.0).astype(np.float32)

            phase_base = np.cos(subcarrier_idx * 0.1) * 1.5 + np.random.normal(0, 0.1, self.TARGET_SUBCARRIERS)
            phases = phase_base.astype(np.float32)

            with self._window_lock:
                self.raw_frame_buffer.append(amps)
                self.phase_frame_buffer.append(phases)

            if self.is_recording:
                self.recorded_frames.append({
                    "timestamp": time.time(),
                    "sequence": self.packets_received + 1,
                    "rssi": carrier_rssi,
                    "noise": -95.0,
                    "amplitudes": amps.tolist(),
                    "phases": phases.tolist()
                })

            self.packets_received += 1
            self.current_rssi = carrier_rssi
            self.packet_rate_hz = 30.0


# Global Singleton Instance for Backend Integration
real_csi_collector = RealCSICollector(auto_connect=False)
