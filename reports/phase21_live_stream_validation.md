# CSIFormer Phase 21.1 — Live Stream Validation Report

## Executive Summary

This report establishes empirical proof of **live physical CSI streaming** from the ESP32-S3 microcontroller on `COM5` and documents the verification metrics under active RF stimulation.

Using the extended 15.0-second hardware verification utility:
- **18,381 serial bytes** were received across **424 lines**.
- **157 candidate CSI records** were detected and **157 valid CSI packets** were successfully parsed with **0 parsing errors**.
- The physical streaming rate was measured at **$40.4\text{ Hz}$** with **$-56.0\text{ dBm}$ mean RSSI**.
- The streaming diagnostic state reached **`CSI_STREAM_ACTIVE`**.

Per operator instruction, the subsequent end-to-end physical trial recording is designated as **`PENDING OPERATOR RECORDING`**. No synthetic packets or fabricated sessions were created.

---

## 1. Hardware Verification Command and Execution Output

The verification command was executed on the host system:

```powershell
py -3.11 scratch/run_collection_session.py --verify --port COM5 --duration 15.0
```

### Empirical Hardware Output:
```text
================================================================================
PHASE 21 — HARDWARE VERIFICATION & DIAGNOSTIC CHECK
================================================================================
Testing port COM5 for 15.0s...
[RealCSICollector] Successfully connected to COM5 @ 115200 baud.
[RealCSICollector] Background CSI acquisition loop started.
[RealCSICollector] Disconnected serial interface.
Status:             OK
Diagnostic State:   CSI_STREAM_ACTIVE
Port:               COM5 @ 115200 baud
Connected:          True
Test Duration:      15.0s
Serial Bytes:       18381
Lines Received:     424
Records Detected:   157
Valid CSI Packets:  157
Parsing Errors:     0
CSI Dimensions:     5
Observed Rate:      40.4 Hz
Mean RSSI:          -56.0 dBm
Detected Protocol:  raw_iq_stream

Recent Firmware Messages / Boot Telemetry:
  > I (701) wifi:set rx beacon pti, rx_bcn_pti: 0, bcn_timeout: 25000, mt_pti: 0, mt_time: 10000
  > I (741) wifi:AP's beacon interval = 102400 us, DTIM period = 1
  > I (2521) wifi:<ba-add>idx:1 (ifx:0, 98:ba:5f:ef:28:26), tid:0, ssn:1, winSize:64
  > CSI callback: ESP_OK
  > CSI Receiver Started

Diagnostic State Summary:
  [SUCCESS] Valid physical CSI packets are actively streaming from ESP32-S3.
================================================================================
```

---

## 2. Quantitative Telemetry Metrics

| Diagnostic Metric | Value | Interpretation |
| :--- | :---: | :--- |
| **Serial Port** | `COM5` | WCH CH343 USB-to-UART bridge |
| **Serial Connection** | `True` | Port opened non-blocking, DTR/RTS trap bypassed |
| **Test Duration** | $15.0\text{ s}$ | Accommodates 10.6s boot cycle + 4.4s streaming |
| **Total Serial Bytes** | **18,381 bytes** | Active UART transmission |
| **Total Lines Received** | **424 lines** | Bootloader logs + Wi-Fi state machine + CSI records |
| **Records Detected** | **157 records** | Lines matching candidate `RSSI=` / `CSI:` pattern |
| **Valid Packets Parsed** | **157 packets** | Successfully parsed into numeric IQ arrays |
| **Parsing Errors** | **0 errors** | 100% parsing success rate ($0.0\%$ error rate) |
| **Raw Subcarrier Count** | **5 channels** | First 5 complex subcarrier bins ($10\text{ integers}$) |
| **Observed Sampling Rate** | **$40.4\text{ Hz}$** | Sustained rate exceeding $30\text{ Hz}$ minimum target |
| **Mean RSSI** | **$-56.0\text{ dBm}$** | Strong RF signal from AP `Tp link` |
| **Diagnostic State** | **`CSI_STREAM_ACTIVE`** | Live acquisition verified |

---

## 3. End-to-End Physical Recording Acceptance Test Status

In Section 4 of the Phase 21.1 mandate, the end-to-end recording acceptance test requires:
1. Verifying active live CSI packet reception (achieved: 157 packets @ $40.4\text{ Hz}$).
2. Conducting an ordinary activity trial with a genuine physical participant.
3. Saving and validating the recording file via [`DatasetIntegrityValidator`](file:///c:/Users/saifu/Desktop/4-1%20project/backend/app/services/session_validator.py).
4. Updating the dataset manifest only upon successful validation.

### Current Status:
**Status:** **`PENDING OPERATOR RECORDING`**

### Evidence and Safeguards:
- Confirmed by the operator via interactive consultation.
- In strict adherence to the non-fabrication constraint, **no synthetic sessions, mock data, or phantom participants were injected**.
- The physical acquisition pipeline is ready and verified.
- The 23 historical sessions and 3,212 packets remain completely intact and unpolluted.

---

## 4. Exact Operator Execution Procedure

To execute the live physical recording trial, the human operator should run the following commands:

### Step 1: Ensure Wi-Fi AP is Active
Confirm that the 2.4 GHz Access Point named **`Tp link`** is operating on **Channel 7** within 3–5 meters of the ESP32-S3.

### Step 2: Record a 4-Second Walking Trial
Position the physical participant (`Participant_03`) at the 2.5 m baseline and execute:
```powershell
py -3.11 scratch/run_collection_session.py --activity walk --participant Participant_03 --duration 4.0 --room Laboratory --distance 2.5 --confirm
```
*Note: The acquisition engine will automatically wait through the boot sequence until the first live CSI packet arrives, then capture exactly 4.0 seconds ($\sim 160\text{ frames}$) of walking data.*

### Step 3: Validate the Newly Recorded Session
Run the integrity validator:
```powershell
py -3.11 scratch/run_collection_session.py --validate
```
**Expected Output:**
- `Manifest Status: VALID`
- `Total Sessions: 24`
- `Total Packets: ~3,372`
- `Distinct Participants: ['Participant_01', 'Participant_02', 'Participant_03']`
