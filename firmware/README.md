# ESP32-S3 Wi-Fi CSI Hardware Firmware — CSIFormer Phase 02

This directory contains the production-grade C firmware for **ESP32-S3** microcontroller boards to capture raw Wi-Fi Channel State Information (CSI) subcarrier telemetry.

---

## 🛠️ Hardware Requirements

- **ESP32-S3 Development Board** (ESP32-S3-DevKitC-1 or N8R8 / N16R8 variant).
- **USB Type-C Data Cable** (connected to ESP32-S3 High-Speed USB / UART port).
- **2.4 GHz / 5 GHz Wi-Fi Transmitter** (or additional ESP32-S3 TX Beacon).

---

## ⚡ Quick Flashing Instructions

### Method 1: Using ESP-IDF CLI
```bash
cd firmware/esp32s3_csi_collector
idf.py set-target esp32s3
idf.py build
idf.py -p COM3 flash monitor
```

### Method 2: Using PlatformIO CLI
```bash
cd firmware/esp32s3_csi_collector
pio run --target upload
pio device monitor --baud 921600
```

---

## 📡 Output Telemetry Protocol

The firmware outputs ASCII telemetry formatted as:
`CSI_DATA,<mac>,<rssi>,<noise_floor>,<sequence>,<num_subcarriers>,[amp_0:phase_0,amp_1:phase_1,...]`

- **Baud Rate:** `921600 baud`
- **UDP Port:** `5555`
