export interface CSIPoint3D {
  x: number;
  y: number;
  z: number;
  intensity: number;
  doppler: number;
}

export interface CSIPacketFrame {
  node_id: string;
  sequence: number;
  timestamp: number;
  subcarrier_count: number;
  amplitudes: number[];
  phases: number[];
  rssi: number;
  noise_floor: number;
  snr: number;
}

export type SupportedActivity =
  | 'Empty Room'
  | 'Standing'
  | 'Sitting'
  | 'Walking'
  | 'Running'
  | 'Falling'
  | 'Lying Down'
  | 'Multiple Persons';

export interface ActivityPrediction {
  timestamp: number;
  activity: SupportedActivity | string;
  confidence: number;
  presence: boolean;
  probabilities: Record<string, number>;
  anomaly_detected: boolean;
  anomaly_type?: string;
  is_unvalidated?: boolean;
  latency_ms?: number;
  buffering?: boolean;
  buffered_frames?: number;
  required_frames?: number;
  gate_weights?: { raw: number; doppler: number };
}

export interface NodeInfo {
  id: string;
  name: string;
  role: 'receiver' | 'transmitter';
  ip: string;
  mac: string;
  x: number;
  y: number;
  z: number;
  status: 'active' | 'idle' | 'offline';
  subcarriers: number;
  rssi: number;
}

export interface TargetPosition3D {
  x: number;
  y: number;
  z: number;
  vx: number;
  vy: number;
  vz: number;
  confidence: number;
  zone: string;
  timestamp: number;
}

export interface SystemMetrics {
  uptime_seconds: number;
  packets_processed: number;
  packet_rate_hz: number;
  active_nodes_count: number;
  total_nodes_count: number;
  cpu_usage_pct: number;
  memory_usage_pct: number;
  ws_connections_count: number;
  stream_latency_ms: number;
}

export interface SpatialTelemetryFrame {
  type: 'csi_spatial_telemetry_frame';
  timestamp: number;
  data_source?: 'LIVE HARDWARE' | 'RECORDED REPLAY' | 'SIMULATION' | string;
  is_real_measurement?: boolean;
  target: TargetPosition3D;
  point_cloud: CSIPoint3D[];
  frames: Record<string, CSIPacketFrame>;
  activity: ActivityPrediction;
  nodes: NodeInfo[];
  hardware?: any;
  subcarriers?: any;
}

export type RenderingMode = 'production' | 'research' | 'debug';

export interface SpatialVisibilitySettings {
  renderingMode?: RenderingMode;
  showGrid: boolean;
  showNodes: boolean;
  showPointCloud: boolean;
  showBeams: boolean;
  showAvatar: boolean;
  showTrajectory: boolean;
  showHeatmap: boolean;
  showNavMesh?: boolean;
  autoRotate: boolean;
}

export interface DatasetSessionStatus {
  is_recording: boolean;
  is_paused: boolean;
  session_id: string | null;
  activity_class: string;
  subject_id: string;
  room_name: string;
  elapsed_seconds: number;
  recorded_frames: number;
  packet_loss_pct: number;
  quality_level: 'Excellent' | 'Good' | 'Acceptable' | 'Poor' | 'Invalid';
  composite_quality_score: number;
  avg_snr: number;
  avg_rssi: number;
}

export interface DatasetClassStats {
  folder: string;
  recordings_count: number;
  frames_count: number;
  storage_bytes: number;
  duration_seconds: number;
}

export interface DatasetDashboardStats {
  dataset_root: string;
  total_recordings: number;
  total_frames: number;
  total_subjects: number;
  total_duration_seconds: number;
  total_storage_bytes: number;
  storage_mb: number;
  class_balance_score_pct: number;
  status_indicator: 'HEALTHY' | 'NEEDS MORE DATA' | 'CLASS IMBALANCE DETECTED';
  missing_classes: string[];
  class_distribution: Record<string, DatasetClassStats>;
}

export interface ResearchReadinessReport {
  readiness_level: string;
  readiness_score_pct: number;
  dataset_statistics: DatasetDashboardStats;
  missing_categories_count: number;
  recommendations: string[];
  generated_timestamp: number;
}


