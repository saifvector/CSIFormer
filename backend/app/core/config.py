import os

class Settings:
    PROJECT_NAME: str = "CSIFormer Spatial Intelligence Platform"
    PROJECT_VERSION: str = "1.0.0-spatial"
    API_V1_STR: str = "/api/v1"
    
    CORS_ORIGINS: list = ["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000", "*"]
    
    # 3D Room Bounds (meters)
    ROOM_WIDTH: float = 10.0
    ROOM_LENGTH: float = 8.0
    ROOM_HEIGHT: float = 3.5
    
    # CSI Parameters
    DEFAULT_SUBCARRIER_COUNT: int = 64
    DEFAULT_SAMPLING_RATE_HZ: float = 30.0
    
    # Initial 3D Node Anchors
    INITIAL_NODES: list = [
        {"id": "esp32-rx-01", "name": "ESP32-S3 RX East", "role": "receiver", "ip": "192.168.1.101", "mac": "70:04:1D:82:11:0A", "x": 1.5, "y": 1.2, "z": 1.5, "status": "active"},
        {"id": "esp32-rx-02", "name": "ESP32-S3 RX West", "role": "receiver", "ip": "192.168.1.102", "mac": "70:04:1D:82:11:0B", "x": 8.5, "y": 1.2, "z": 1.5, "status": "active"},
        {"id": "esp32-rx-03", "name": "ESP32-S3 RX South", "role": "receiver", "ip": "192.168.1.103", "mac": "70:04:1D:82:11:0C", "x": 5.0, "y": 7.5, "z": 1.5, "status": "active"},
        {"id": "esp32-tx-01", "name": "ESP32-S3 TX Beacon", "role": "transmitter", "ip": "192.168.1.100", "mac": "70:04:1D:82:11:00", "x": 5.0, "y": 0.8, "z": 2.5, "status": "active"}
    ]

settings = Settings()
