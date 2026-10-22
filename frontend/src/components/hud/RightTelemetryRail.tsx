import React, { useState } from 'react';
import { Target, Cpu, FlaskConical, Play, Square, ShieldCheck } from 'lucide-react';
import { startExperiment, stopExperiment } from '../../services/api';
import { collisionManager } from '../../services/spatial/CollisionManager';
import { navMeshEngine } from '../../services/spatial/NavMeshEngine';
import type { TargetPosition3D, NodeInfo } from '../../types/csi';

interface RightTelemetryRailProps {
  target: TargetPosition3D | null;
  tracking?: {
    speed_ms?: number;
    total_distance_m?: number;
    stability_pct?: number;
    predicted_vector?: { x: number; y: number };
  } | null;
  hardware?: any;
  subcarriers?: any;
  nodes?: NodeInfo[];
  experimentStatus?: {
    status?: string;
  } | null;
  dataSource?: string;
}

export const RightTelemetryRail: React.FC<RightTelemetryRailProps> = ({
  target,
  tracking,
  hardware,
  subcarriers,
  experimentStatus,
  dataSource,
}) => {
  const [selectedExp, setSelectedExp] = useState<string>('exp_01');
  const [isRecording, setIsRecording] = useState<boolean>(false);

  const tx = target?.x ? (target.x).toFixed(2) : '4.59';
  const ty = target?.y ? (target.y).toFixed(2) : '2.16';
  const tz = target?.z ? (target.z).toFixed(2) : '1.02';
  const speed = tracking?.speed_ms ? tracking.speed_ms.toFixed(2) : '1.26';
  const stability = tracking?.stability_pct ?? 98.6;

  // Real-time spatial collision metrics
  const threeX = (target?.x ?? 5.0) - 5.0;
  const threeZ = (target?.y ?? 4.0) - 4.0;
  const colRes = collisionManager.testPointCollision(threeX, threeZ);
  const navStats = navMeshEngine.getWalkableStats();

  const collisionStatus = colRes.isColliding
    ? (colRes.nearestCollider?.isRestricted ? 'RESTRICTED' : 'LOCALIZATION REFINED')
    : (colRes.closestDistance < 0.40 ? 'AVOIDING OBSTACLE' : 'OCCUPANCY VERIFIED');

  const isReal = subcarriers?.is_real_measurement || hardware?.is_real_measurement || false;
  const sourceLabel = dataSource || hardware?.source_label || (isReal ? 'REAL CSI' : 'SIMULATION');
  const validFrames = hardware?.valid_frames ?? hardware?.packets_received ?? 0;
  const parseFailures = hardware?.parse_failures ?? 0;
  const packetRateHz = hardware?.packet_rate_hz ?? (hardware?.devices?.[0]?.packet_rate_hz ?? 0);
  const rssi = subcarriers?.rssi ?? hardware?.devices?.[0]?.rssi ?? -61;
  const noiseFloor = subcarriers?.noise_floor ?? -92;
  const lastPacketTime = hardware?.last_packet_time
    ? new Date(hardware.last_packet_time * 1000).toLocaleTimeString()
    : 'Active';

  const rawAmps: number[] = subcarriers?.amplitudes || [];
  const amps = rawAmps.length > 0
    ? rawAmps
    : Array.from({ length: 64 }, (_, i) => 15.0 + Math.sin(i * 0.2) * 4.0);

  const isExpActive = experimentStatus?.status === 'recording' || isRecording;

  const handleStart = async () => {
    try {
      setIsRecording(true);
      await startExperiment(selectedExp);
    } catch (err) {
      console.warn("Experiment start error:", err);
    }
  };

  const handleStop = async () => {
    try {
      setIsRecording(false);
      await stopExperiment();
    } catch (err) {
      console.warn("Experiment stop error:", err);
    }
  };

  return (
    <div className="w-80 h-full bg-[#081120]/95 border-l border-[#00F0FF]/20 p-4 font-mono text-xs text-[#E2F8FF] space-y-4 overflow-y-auto pointer-events-auto shadow-2xl flex flex-col justify-between">
      <div className="space-y-4">
        {/* Section 1: 3D Spatial Localization & Kinematics */}
        <div className="space-y-2">
          <div className="flex items-center justify-between pb-1 border-b border-slate-800">
            <div className="flex items-center space-x-2 text-[#00F0FF]">
              <Target className="w-4 h-4" />
              <h3 className="text-xs font-black uppercase tracking-widest text-[#E2F8FF]">3D Kinematics</h3>
            </div>
            <span className={`text-[9px] px-2 py-0.5 rounded font-bold border ${
              isReal
                ? 'bg-amber-950 text-amber-300 border-amber-600'
                : 'bg-cyan-950 text-[#00F0FF] border-[#00F0FF]/40'
            }`}>
              {isReal ? 'UNAVAILABLE' : '30 FPS KALMAN'}
            </span>
          </div>

          {isReal ? (
            <div className="p-3 rounded-xl bg-amber-950/30 border border-amber-600/30 text-[10px] text-amber-300">
              <p className="font-bold">Localization unavailable</p>
              <p className="text-amber-400/70 mt-1">Single 1×1 SISO receiver cannot determine AoA or 3D coordinates. Coordinates, speed, and stability require multi-anchor deployment.</p>
            </div>
          ) : (
            <>
              {/* Coordinates Grid */}
              <div className="grid grid-cols-3 gap-1 text-center font-bold text-[10px]">
                <div className="p-2 rounded-lg bg-[#020617] border border-slate-800">
                  <span className="block text-[8px] text-[#94A3B8]">X COORD</span>
                  <span className="text-[#00F0FF] text-xs">{tx} m</span>
                </div>
                <div className="p-2 rounded-lg bg-[#020617] border border-slate-800">
                  <span className="block text-[8px] text-[#94A3B8]">Y COORD</span>
                  <span className="text-[#00F0FF] text-xs">{ty} m</span>
                </div>
                <div className="p-2 rounded-lg bg-[#020617] border border-slate-800">
                  <span className="block text-[8px] text-[#94A3B8]">HEIGHT Z</span>
                  <span className="text-[#00F0FF] text-xs">{tz} m</span>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2 text-[10px]">
                <div className="p-2.5 rounded-xl bg-[#020617] border border-slate-800">
                  <span className="text-[8px] text-[#94A3B8] uppercase tracking-widest block font-bold">Speed</span>
                  <span className="text-sm font-black text-emerald-400">{speed} m/s</span>
                </div>
                <div className="p-2.5 rounded-xl bg-[#020617] border border-slate-800">
                  <span className="text-[8px] text-[#94A3B8] uppercase tracking-widest block font-bold">Stability</span>
                  <span className="text-sm font-black text-[#00F0FF]">{stability}%</span>
                </div>
              </div>
            </>
          )}
        </div>

        {!isReal && (
          <div className="space-y-2 pt-2 border-t border-slate-800">
            <div className="flex items-center justify-between pb-1 border-b border-slate-800">
              <div className="flex items-center space-x-2 text-[#00F0FF]">
                <ShieldCheck className="w-4 h-4" />
                <h3 className="text-xs font-black uppercase tracking-widest text-[#E2F8FF]">Spatial Collision</h3>
              </div>
              <span
                className={`text-[9px] px-2 py-0.5 rounded font-bold border ${
                  collisionStatus === 'OCCUPANCY VERIFIED'
                    ? 'bg-emerald-950 text-emerald-400 border-emerald-700/50'
                    : collisionStatus === 'AVOIDING OBSTACLE'
                    ? 'bg-amber-950 text-amber-300 border-amber-500/50 animate-pulse'
                    : collisionStatus === 'LOCALIZATION REFINED'
                    ? 'bg-cyan-950 text-cyan-300 border-cyan-500/50'
                    : 'bg-rose-950 text-rose-300 border-rose-600/50'
                }`}
              >
                {collisionStatus}
              </span>
            </div>

            <div className="grid grid-cols-2 gap-2 text-[10px]">
              <div className="p-2.5 rounded-xl bg-[#020617] border border-slate-800">
                <span className="text-[8px] text-[#94A3B8] uppercase tracking-widest block font-bold">NavMesh Area</span>
                <span className="text-sm font-black text-[#00F0FF]">{navStats.walkablePct.toFixed(1)}%</span>
              </div>
              <div className="p-2.5 rounded-xl bg-[#020617] border border-slate-800">
                <span className="text-[8px] text-[#94A3B8] uppercase tracking-widest block font-bold">Nearest Obstacle</span>
                <span className="text-xs font-bold text-slate-200 truncate block">
                  {colRes.nearestCollider?.name ? colRes.nearestCollider.name.split(' ')[0] : 'Clear'}
                </span>
              </div>
            </div>
          </div>
        )}

        {/* Section 2: ESP32 Hardware Status & Subcarrier Inspector */}
        <div className="space-y-2 pt-2 border-t border-slate-800">
          <div className="flex items-center justify-between pb-1 border-b border-slate-800">
            <div className="flex items-center space-x-2 text-[#00F0FF]">
              <Cpu className="w-4 h-4" />
              <h3 className="text-xs font-black uppercase tracking-widest text-[#E2F8FF]">
                {isReal ? 'Hardware & CSI Profile' : 'ESP32 Hardware'}
              </h3>
            </div>
            <span className={`text-[9px] font-bold px-2 py-0.5 rounded border ${
              isReal
                ? 'text-emerald-300 bg-emerald-950 border-emerald-600'
                : 'text-cyan-300 bg-cyan-950 border-cyan-800'
            }`}>
              {sourceLabel}
            </span>
          </div>

          {/* Real Metrics Grid */}
          <div className="grid grid-cols-2 gap-1.5 text-[10px]">
            <div className="p-2 rounded-lg bg-[#020617] border border-slate-800">
              <span className="text-[8px] text-[#94A3B8] uppercase tracking-widest block font-bold">Valid Frames</span>
              <span className="text-xs font-bold text-emerald-400">
                {validFrames} {parseFailures > 0 ? `(${parseFailures} fail)` : ''}
              </span>
            </div>
            <div className="p-2 rounded-lg bg-[#020617] border border-slate-800">
              <span className="text-[8px] text-[#94A3B8] uppercase tracking-widest block font-bold">Packet Rate</span>
              <span className="text-xs font-bold text-[#00F0FF]">{packetRateHz.toFixed(1)} Hz</span>
            </div>
            <div className="p-2 rounded-lg bg-[#020617] border border-slate-800">
              <span className="text-[8px] text-[#94A3B8] uppercase tracking-widest block font-bold">RF Signal / Noise</span>
              <span className="text-xs font-bold text-slate-200">{rssi} dBm / {noiseFloor} dBm</span>
            </div>
            <div className="p-2 rounded-lg bg-[#020617] border border-slate-800">
              <span className="text-[8px] text-[#94A3B8] uppercase tracking-widest block font-bold">Timestamp</span>
              <span className="text-xs font-bold text-slate-300 truncate block">{lastPacketTime}</span>
            </div>
          </div>

          {/* Subcarrier Signal Chart */}
          <div className="p-2.5 rounded-xl bg-[#020617] border border-slate-800 space-y-1.5">
            <div className="flex justify-between text-[9px] font-bold">
              <span className={isReal ? 'text-emerald-400' : 'text-[#00F0FF]'}>
                {isReal ? 'Physical Measured Subcarriers' : '64 Subcarrier Profile'}
              </span>
              <span className="text-[#94A3B8]">
                {amps.length} subcarriers {isReal ? '(Format B)' : '(20 MHz)'}
              </span>
            </div>
            <div className="h-16 w-full flex items-end justify-between gap-[1px] bg-slate-950 p-1.5 rounded-md border border-slate-800">
              {amps.map((amp, idx) => {
                const maxVal = isReal ? 35.0 : 30.0;
                const h = Math.min(100, Math.max(8, (amp / maxVal) * 100));
                return (
                  <div
                    key={idx}
                    className={`w-full rounded-t-sm ${
                      isReal ? 'bg-gradient-to-t from-emerald-500 to-cyan-400' : 'bg-[#00F0FF]/80'
                    }`}
                    style={{ height: `${h}%` }}
                    title={`Subcarrier #${idx}: amp=${amp.toFixed(1)}`}
                  ></div>
                );
              })}
            </div>
          </div>
        </div>

        {/* Section 3: Experiment Protocol Manager */}
        <div className="space-y-2 pt-2 border-t border-slate-800">
          <div className="flex items-center justify-between pb-1 border-b border-slate-800">
            <div className="flex items-center space-x-2 text-[#00F0FF]">
              <FlaskConical className="w-4 h-4" />
              <h3 className="text-xs font-black uppercase tracking-widest text-[#E2F8FF]">Experiment Protocol</h3>
            </div>
            <span className={`text-[9px] px-2 py-0.5 rounded font-bold border ${isExpActive ? 'bg-rose-950 text-rose-300 border-rose-700 animate-pulse' : 'bg-slate-900 text-[#94A3B8] border-slate-800'}`}>
              {isExpActive ? 'RECORDING' : 'IDLE'}
            </span>
          </div>

          <select
            value={selectedExp}
            onChange={(e) => setSelectedExp(e.target.value)}
            disabled={isExpActive}
            className="w-full bg-[#020617] border border-slate-800 text-[#E2F8FF] rounded-lg p-1.5 text-[10px] focus:outline-none focus:border-[#00F0FF]"
          >
            <option value="exp_01">Exp 01: Empty Room Baseline (60s)</option>
            <option value="exp_02">Exp 02: Static Postures (120s)</option>
            <option value="exp_03">Exp 03: Dynamic Motion (180s)</option>
            <option value="exp_04">Exp 04: Multi-Person Tracking (240s)</option>
          </select>

          {!isExpActive ? (
            <button
              onClick={handleStart}
              className="w-full py-2 rounded-xl bg-gradient-to-r from-[#00F0FF] to-[#00BFFF] text-slate-950 font-black flex items-center justify-center space-x-1.5 shadow-lg shadow-[#00F0FF]/20 hover:brightness-110 transition-all text-[11px]"
            >
              <Play className="w-3.5 h-3.5 fill-current" />
              <span>Launch Experiment</span>
            </button>
          ) : (
            <button
              onClick={handleStop}
              className="w-full py-2 rounded-xl bg-rose-600 text-white font-black flex items-center justify-center space-x-1.5 shadow-lg shadow-rose-600/20 transition-all text-[11px]"
            >
              <Square className="w-3.5 h-3.5 fill-current" />
              <span>Stop Protocol</span>
            </button>
          )}
        </div>
      </div>

      <div className="pt-2 border-t border-slate-800 text-[9px] text-[#94A3B8] text-center">
        <span>PALANTIR / LATTICE COMMAND MATRIX</span>
      </div>
    </div>
  );
};
