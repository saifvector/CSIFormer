# Phase 60: Real Detection Readiness Report

**Date:** 2026-10-21  
**Author:** Antigravity Agent (automated audit)  
**Status:** Stage B & D — Truthful UI + Backend Enforcement Complete

---

## Executive Summary

Phase 60 transforms CSIFormer from a simulation-heavy visual dashboard into a 
system that **truthfully represents its capabilities** when operating on real 
Wi-Fi CSI data from an ESP32-S3 receiver.

All changes enforce a strict separation between **real measurement mode** 
(LIVE HARDWARE / RECORDED REPLAY) and **simulation mode**, ensuring no 
simulated or hardcoded values are presented as real measurements.

---

## Stage A — Full Data-Path Audit Findings

### 11 Misleading Components Identified

| # | Component | Issue | Severity |
|---|-----------|-------|----------|
| 1 | 3D Localization | Single 1×1 SISO receiver cannot determine AoA or multilaterate — falls back to simulation coordinates presented as real | **CRITICAL** |
| 2 | Absence Detection | 0 empty-room sessions in canonical dataset → no True Negative baseline (FPR undefined) | **CRITICAL** |
| 3 | Subcarrier Interpolation | UART buffer overflow truncates CSI lines to ~5 subcarrier pairs; `np.interp` fabricated 51 channels from 5 data points | **CRITICAL** |
| 4 | Multi-Person Tracking | Synthetic multi-target generation from single-node SISO with no basis in measured data | HIGH |
| 5 | Digital Twin Zones | 6 hardcoded semantic zones with simulated occupancy, dwell times, utilization presented as measured | HIGH |
| 6 | Point Cloud Generation | Volumetric 3D reconstruction impossible from single receiver — purely synthetic | HIGH |
| 7 | Room Event Detector | Zone violations, restricted-area alerts based on simulated position, not measured | MEDIUM |
| 8 | Spatial Insights Engine | Space utilization percentages derived from simulated trajectories | MEDIUM |
| 9 | Trajectory Ribbon | Path visualization from simulated coordinates | MEDIUM |
| 10 | Ground Heatmap | Occupancy heatmap from simulated movement patterns | MEDIUM |
| 11 | Collision/NavMesh Engine | Obstacle avoidance computed against simulated position | LOW |

### Model Evaluation (Canonical Dataset)

| Model | Test Accuracy | Macro-F1 |
|-------|-------------|----------|
| Phase 13 (`csiformer_phase13_best.pth`) | 22.73% (5/22) | < 0.18 |
| Phase 15 (`csiformer_phase15_adapted.pth`) | 22.73% (5/22) | < 0.18 |

Both models collapse predictions or scatter across classes. No model currently 
performs above chance on the canonical test split.

---

## Stage B — Backend Enforcement (Completed)

### `hardware_bridge.py` Changes

1. **Truncated Frame Rejection** (ESP32S3CSISerialProvider):
   - Lines with < 52 subcarrier pairs are now dropped with `parse_failures++`
   - Previously: `np.interp` fabricated 51 channels from as few as 5 data points
   - Now: Only frames with ≥ 52 subcarriers are accepted; 52–55 are interpolated to 56; 56 pass through; 64 are tone-mapped to 56

2. **Truthful Localization** (ESP32S3CSISerialProvider + RecordedCSISessionProvider):
   - `get_target_3d()` returns `(0,0,0)` with `confidence=0.0` and `zone="LOCALIZATION UNAVAILABLE (Single RX Node)"` / `"LOCALIZATION UNAVAILABLE (Recorded Replay)"`
   - `generate_point_cloud()` returns empty list `[]`

3. **Parse Failure Telemetry**:
   - `get_hardware_status()` now includes `parse_failures` and `valid_frames` counters
   - Per-device status also includes `parse_failures`

### `main.py` Stream Loop Changes

When `is_real_measurement` is true:
- **Suppressed:** localization engine smoothing, multi-person tracker, digital twin zones, room event detector, spatial insight engine, room memory service, point cloud generation
- **Preserved:** real CSI frame acquisition, subcarrier inspection, hardware status, model inference (marked `is_unvalidated: true`)
- **Added:** `target.available = false`, `target.status`, `tracking.available = false`, `multiperson.available = false`, `digital_twin.available = false`

---

## Stage D — Frontend Truthful UI (Completed)

### `SpatialCanvas3D.tsx`
- **Hidden in real mode:** Human avatar, point cloud, trajectory ribbon, ground heatmap, RF beams
- **Added:** Amber watermark overlay: "3D LOCALIZATION UNAVAILABLE — Single SISO receiver — AoA/multilateration requires multi-anchor deployment"
- **Preserved:** Room geometry, sensor node positions (without simulated target beams)

### `LeftIntelligenceRail.tsx`
- **Activity buttons:** Disabled in real mode (they control simulation, not detection)
- **Digital Twin zones:** Replaced with "Zone tracking unavailable" message in real mode
- **Utilization score:** Shows 0% instead of hardcoded 82.5% fallback

### `RightTelemetryRail.tsx`
- **3D Kinematics section:** Shows "UNAVAILABLE" badge and explanation in real mode
- **Collision/NavMesh section:** Entirely hidden in real mode
- **Hardware telemetry:** Always visible (shows real data)
- **Subcarrier chart:** Always visible (shows real amplitudes/phases)

### `SpatialHeaderHUD.tsx`
- Already correctly differentiates LIVE HARDWARE / RECORDED REPLAY / SIMULATION
- Shows "Measured CSI (Real)" vs "Synthetic RF Model" sub-label

---

## What Works Today

| Feature | Status | Evidence |
|---------|--------|----------|
| ESP32-S3 passive CSI capture (COM5) | ✅ Works | Verified in Phase 59.3 |
| Serial line parsing (Format B v1) | ✅ Works | Parser handles CSI_DATA lines |
| Truncated frame rejection | ✅ Fixed | < 52 subcarriers → parse_failures++ |
| Real-time subcarrier visualization | ✅ Works | RightTelemetryRail shows live amplitudes |
| Hardware status telemetry | ✅ Works | Packet rate, RSSI, noise floor, SNR |
| Model inference on live CSI | ⚠️ Runs but unvalidated | 22.73% accuracy on canonical test set |
| Recorded session replay | ✅ Works | RecordedCSISessionProvider at 30 Hz |
| Simulation mode | ✅ Works | Full 3D visualization with synthetic data |

## What Does Not Work

| Feature | Status | Reason |
|---------|--------|--------|
| 3D localization | ❌ Unavailable | Single 1×1 SISO receiver — no AoA/multilateration |
| Multi-person tracking | ❌ Unavailable | Requires multi-antenna spatial diversity |
| Zone occupancy detection | ❌ Unavailable | Depends on localization |
| Point cloud reconstruction | ❌ Unavailable | Single node cannot reconstruct volume |
| Activity classification | ⚠️ Unvalidated | Model exists but accuracy is 22.73% (≈ random) |
| Fall detection | ⚠️ Unvalidated | No ground-truth fall events in test set |
| Absence/empty room detection | ❌ No baseline | 0 empty-room sessions in canonical dataset |

---

## Recommended Next Steps

1. **Collect empty-room calibration sessions** (authorized separately) to establish True Negative baseline
2. **Investigate UART baud rate** — 115200 may be insufficient for 64-subcarrier HT20 output; consider 921600
3. **Retrain model** with properly recorded, non-truncated CSI frames after fixing data pipeline
4. **Add ground-truth labeling pipeline** for live activity validation
5. **Multi-anchor deployment** (3+ ESP32-S3 nodes) required for any spatial localization claims

---

## Protected Artifacts (Unchanged)

| File | MD5 |
|------|-----|
| `models/csiformer_phase13_best.pth` | `383b4d98c08f8970b0443738f170ec01` |
| `models/csiformer_phase15_adapted.pth` | `ab3d97a04d78edf75d807178772bc828` |
| `data/real_csi_dataset/dataset_manifest.json` | `a58e1280fb2c0a6649335a9a381d00c6` |
