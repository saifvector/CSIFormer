import type { SystemMetrics, NodeInfo } from '../types/csi';

const API_BASE = 'http://localhost:8000/api/v1';

export async function fetchSystemStatus(): Promise<SystemMetrics> {
  const res = await fetch(`${API_BASE}/system/status`);
  if (!res.ok) throw new Error('Failed to fetch system status');
  return res.json();
}

export async function setSimulatedActivity(activity: string, noiseLevel: number = 0.05) {
  const res = await fetch(`${API_BASE}/csi/simulation/activity`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ activity, noise_level: noiseLevel }),
  });
  if (!res.ok) throw new Error('Failed to set simulated activity');
  return res.json();
}

export async function fetchHardwareStatus() {
  const res = await fetch(`${API_BASE}/hardware/devices`);
  if (!res.ok) throw new Error('Failed to fetch hardware status');
  return res.json();
}

export async function setHardwareSource(mode: string) {
  const res = await fetch(`${API_BASE}/csi/hardware/source`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mode }),
  });
  if (!res.ok) throw new Error('Failed to set hardware source');
  return res.json();
}

export async function fetchNodes(): Promise<NodeInfo[]> {
  const res = await fetch(`${API_BASE}/localization/nodes`);
  if (!res.ok) throw new Error('Failed to fetch nodes');
  return res.json();
}

export async function startRecording(data: { name: string; activity_label: string; subject_id: string }) {
  const res = await fetch(`${API_BASE}/datasets/record/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error('Failed to start recording');
  return res.json();
}

export async function stopRecording() {
  const res = await fetch(`${API_BASE}/datasets/record/stop`, {
    method: 'POST',
  });
  if (!res.ok) throw new Error('Failed to stop recording');
  return res.json();
}

export async function fetchRecordingStatus() {
  const res = await fetch(`${API_BASE}/datasets/record/status`);
  if (!res.ok) throw new Error('Failed to fetch recording status');
  return res.json();
}

export async function startExperiment(exp_id: string) {
  const res = await fetch(`${API_BASE}/hardware/experiments/start?exp_id=${exp_id}`, {
    method: 'POST',
  });
  if (!res.ok) throw new Error('Failed to start experiment');
  return res.json();
}

export async function stopExperiment() {
  const res = await fetch(`${API_BASE}/hardware/experiments/stop`, {
    method: 'POST',
  });
  if (!res.ok) throw new Error('Failed to stop experiment');
  return res.json();
}

// =========================================================================
// PHASE 09: ADVANCED DATASET ACQUISITION & ANALYTICS CLIENT METHODS
// =========================================================================

export interface StartDatasetSessionParams {
  activity_class: string;
  subject_id: string;
  room_name?: string;
  room_size?: string;
  router_id?: string;
  router_location?: string;
  experiment_id?: string;
  notes?: string;
  custom_session_id?: string;
}

export async function startDatasetSession(params: StartDatasetSessionParams) {
  const res = await fetch(`${API_BASE}/datasets/session/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });
  if (!res.ok) throw new Error('Failed to start dataset session');
  return res.json();
}

export async function pauseDatasetSession() {
  const res = await fetch(`${API_BASE}/datasets/session/pause`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to pause dataset session');
  return res.json();
}

export async function resumeDatasetSession() {
  const res = await fetch(`${API_BASE}/datasets/session/resume`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to resume dataset session');
  return res.json();
}

export async function stopDatasetSession() {
  const res = await fetch(`${API_BASE}/datasets/session/stop`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to stop dataset session');
  return res.json();
}

export async function cancelDatasetSession() {
  const res = await fetch(`${API_BASE}/datasets/session/cancel`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to cancel dataset session');
  return res.json();
}

export async function fetchDatasetSessionStatus() {
  const res = await fetch(`${API_BASE}/datasets/session/status`);
  if (!res.ok) throw new Error('Failed to fetch dataset session status');
  return res.json();
}

export async function fetchDatasetDashboard() {
  const res = await fetch(`${API_BASE}/datasets/dashboard`);
  if (!res.ok) throw new Error('Failed to fetch dataset dashboard stats');
  return res.json();
}

export async function fetchReadinessReport() {
  const res = await fetch(`${API_BASE}/datasets/readiness/report`);
  if (!res.ok) throw new Error('Failed to fetch research readiness report');
  return res.json();
}

export function getDatasetExportUrl(sessionId: string, format: 'csv' | 'json' | 'npy') {
  return `${API_BASE}/datasets/export/${sessionId}/${format}`;
}

