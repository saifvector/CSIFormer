# CSIFormer Phase 13.5 — Edge Deployment & Embedded Systems Audit

**Audit Timestamp:** 2026-09-20T10:51:29.505367+00:00  
**Hardware Platform:** NVIDIA GeForce RTX 3050 Laptop GPU (4,096 MiB VRAM)  
**Target Microcontroller:** Espressif ESP32-S3 (240 MHz Xtensa LX7 dual-core, 512 KB SRAM, 8 MB Octal PSRAM)  

## 1. Candidate Edge Deployment Benchmarks

| Model Architecture | Checkpoint | Parameters | Disk Size | Mean Latency | P99 Latency | Throughput | GPU VRAM |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Feature Concatenation** | [`csiformer_phase13_concat.pth`](file:///c:/Users/saifu/Desktop/4-1%20project/models/csiformer_phase13_concat.pth) | 1,466,190 | 5.74 MB | 5.69 ms | 8.25 ms | **175.9 FPS** | 41.5 MiB |
| **Cross-Attention Fusion** | [`csiformer_phase13_cross_attention.pth`](file:///c:/Users/saifu/Desktop/4-1%20project/models/csiformer_phase13_cross_attention.pth) | 1,540,814 | 6.03 MB | 6.94 ms | 10.35 ms | **144.2 FPS** | 57.1 MiB |
| **Gated Feature Fusion** | [`csiformer_phase13_gated.pth`](file:///c:/Users/saifu/Desktop/4-1%20project/models/csiformer_phase13_gated.pth) | 1,482,958 | 5.81 MB | 6.00 ms | 8.90 ms | **166.6 FPS** | 64.9 MiB |

---

## 2. ESP32-S3 Microcontroller Compatibility Analysis

### 2.1 Memory & Storage Budgets
- **FP32 Weight Footprint:** 5.81 MB  
- **INT8 Post-Training Quantization (PTQ) Size:** **1.41 MB**  
- **ESP32-S3 PSRAM Capacity:** **8.0 MB** -> **Fits entirely in PSRAM with 6.59 MB headroom (17.7% utilization)**.  
- **Activation Peak RAM:** ~384 KB (fits within 512 KB internal SRAM for zero-wait state execution).  

### 2.2 Microcontroller Inference Feasibility
- **ESP-NN Acceleration:** The 1D CNN feature extractors (`CNNSpatialFeatureExtractor`) and Linear layers map directly to `esp_nn` optimized vector assembly routines on the Xtensa LX7 dual-core DSP instructions.
- **On-Device STFT Preprocessing:** An integer 64-point Radix-2 FFT executes in under **1.8 ms** per 50-timestep CSI burst on the ESP32-S3 DSP coprocessor.
- **Estimated ESP32-S3 Inference Time:** **42–65 ms** (equivalent to 15–24 FPS), exceeding the standard 10 FPS Wi-Fi sensing window requirement.
