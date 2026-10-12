import React from 'react';
import { Target, Compass, Signal, Zap } from 'lucide-react';
import type { TargetPosition3D } from '../../types/csi';

interface SpatialTelemetryHUDProps {
  target: TargetPosition3D | null;
  snr?: number;
}

export const SpatialTelemetryHUD: React.FC<SpatialTelemetryHUDProps> = ({ target, snr = 34.5 }) => {
  const x = target?.x ?? 4.5;
  const y = target?.y ?? 3.5;
  const z = target?.z ?? 1.0;
  const vx = target?.vx ?? 0.08;
  const vy = target?.vy ?? 0.05;
  const zone = target?.zone ?? 'Center Active Sensing Region';

  return (
    <div className="absolute bottom-6 left-6 z-40 w-80 hud-panel hud-panel-cyan rounded-2xl p-4 font-mono pointer-events-auto transition-all">
      <div className="flex items-center justify-between mb-3 border-b border-slate-800 pb-2">
        <div className="flex items-center space-x-2 text-cyan-400">
          <Target className="w-4 h-4" />
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-100">Spatial Telemetry</h3>
        </div>
        <span className="text-[10px] px-2 py-0.5 rounded bg-cyan-950 text-cyan-300 border border-cyan-800 font-bold">
          3D COORDS
        </span>
      </div>

      {/* 3D Coordinate Grid */}
      <div className="grid grid-cols-3 gap-2 mb-3">
        <div className="bg-slate-900/80 p-2 rounded-xl border border-slate-800 text-center">
          <span className="text-[9px] text-slate-400 block uppercase">X Pos</span>
          <span className="text-base font-black text-cyan-400">{x.toFixed(2)}m</span>
        </div>
        <div className="bg-slate-900/80 p-2 rounded-xl border border-slate-800 text-center">
          <span className="text-[9px] text-slate-400 block uppercase">Y Pos</span>
          <span className="text-base font-black text-indigo-400">{y.toFixed(2)}m</span>
        </div>
        <div className="bg-slate-900/80 p-2 rounded-xl border border-slate-800 text-center">
          <span className="text-[9px] text-slate-400 block uppercase">Z Height</span>
          <span className="text-base font-black text-emerald-400">{z.toFixed(2)}m</span>
        </div>
      </div>

      {/* Velocity & Zone details */}
      <div className="space-y-1.5 text-xs">
        <div className="flex items-center justify-between p-2 rounded-xl bg-slate-900/60 border border-slate-800">
          <div className="flex items-center space-x-1.5 text-slate-400 text-[11px]">
            <Zap className="w-3.5 h-3.5 text-amber-400" />
            <span>Velocity Vector:</span>
          </div>
          <span className="text-slate-200 font-bold">({vx.toFixed(2)}, {vy.toFixed(2)}) m/s</span>
        </div>

        <div className="flex items-center justify-between p-2 rounded-xl bg-slate-900/60 border border-slate-800">
          <div className="flex items-center space-x-1.5 text-slate-400 text-[11px]">
            <Compass className="w-3.5 h-3.5 text-cyan-400" />
            <span>Active Room Zone:</span>
          </div>
          <span className="text-cyan-300 font-bold text-[11px] truncate max-w-[130px]">{zone}</span>
        </div>

        <div className="flex items-center justify-between p-2 rounded-xl bg-slate-900/60 border border-slate-800">
          <div className="flex items-center space-x-1.5 text-slate-400 text-[11px]">
            <Signal className="w-3.5 h-3.5 text-emerald-400" />
            <span>Sensing SNR Ratio:</span>
          </div>
          <span className="text-emerald-400 font-bold">{snr} dB</span>
        </div>
      </div>
    </div>
  );
};
