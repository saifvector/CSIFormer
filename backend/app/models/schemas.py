from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any

class CSIPoint3D(BaseModel):
    x: float
    y: float
    z: float
    intensity: float
    doppler: float

class CSIPacketFrame(BaseModel):
    node_id: str
    sequence: int
    timestamp: float
    subcarrier_count: int = 64
    amplitudes: List[float]
    phases: List[float]
    rssi: float = -50.0
    noise_floor: float = -95.0
    snr: float = 35.0

class ActivityPrediction(BaseModel):
    timestamp: float
    activity: str
    confidence: float
    presence: bool
    probabilities: Dict[str, float]
    anomaly_detected: bool = False
    anomaly_type: Optional[str] = None

class NodeInfo(BaseModel):
    id: str
    name: str
    role: str
    ip: str
    mac: str
    x: float
    y: float
    z: float
    status: str = "active"
    subcarriers: int = 64
    rssi: float = -50.0

class TargetPosition3D(BaseModel):
    x: float
    y: float
    z: float
    vx: float = 0.0
    vy: float = 0.0
    vz: float = 0.0
    confidence: float = 0.98
    zone: str = "Center Active Sensing Region"
    timestamp: float

class SingleTrackState(BaseModel):
    track_id: str
    color: str
    x: float
    y: float
    z: float
    speed_ms: float
    total_distance_m: float
    activity: str
    confidence: float = 0.982
    zone: str = "Workspace Area"
    trajectory_history: List[Dict[str, float]] = []

class MultiPersonTelemetry(BaseModel):
    person_count: int
    occupancy_status: str
    crowd_density_pct: float
    detection_confidence: float
    tracks: List[SingleTrackState]

class SetActivitySimulationRequest(BaseModel):
    activity: str
    noise_level: Optional[float] = 0.05

class SystemMetrics(BaseModel):
    uptime_seconds: float
    packets_processed: int
    packet_rate_hz: float
    active_nodes_count: int
    total_nodes_count: int
    cpu_usage_pct: float
    memory_usage_pct: float
    ws_connections_count: int
    stream_latency_ms: float
