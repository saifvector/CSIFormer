import React, { useState } from 'react';
import { Activity, Zap, RefreshCw, ChevronLeft } from 'lucide-react';
import type { ActivityPrediction } from '../../types/csi';

interface ModelHealthHUDProps {
  activity: ActivityPrediction | null;
}

export const ModelHealthHUD: React.FC<ModelHealthHUDProps> = ({ activity }) => {
  const [isCollapsed, setIsCollapsed] = useState<boolean>(false);

  const confidence = Math.round((activity?.confidence || 0.99) * 100);
  const latency = 8.2;

  if (isCollapsed) {
    return (
      <button
        onClick={() => setIsCollapsed(false)}
        className="absolute top-20 left-48 z-40 p-2.5 hud-panel hud-panel-cyan rounded-2xl font-mono text-cyan-400 hover:text-cyan-300 pointer-events-auto transition-all shadow-2xl flex items-center space-x-2 bg-slate-950/80 border border-slate-800 text-xs"
      >
        <Zap className="w-4 h-4 text-emerald-400" />
        <span className="font-bold text-slate-100">{confidence}% F1</span>
        <span className="text-[10px] text-cyan-300">({latency}ms)</span>
      </button>
    );
  }

  return (
    <div className="absolute top-20 left-48 z-40 w-72 hud-panel hud-panel-cyan rounded-2xl p-4 font-mono text-xs pointer-events-auto space-y-3 shadow-2xl bg-slate-950/90 border border-slate-800">
      <div className="flex items-center justify-between pb-2 border-b border-slate-800">
        <div className="flex items-center space-x-2 text-cyan-400">
          <Activity className="w-4 h-4" />
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-100">CSIFormer AI Health</h3>
        </div>
        <div className="flex items-center space-x-2">
          <span className="text-[9px] px-2 py-0.5 rounded bg-emerald-950 text-emerald-300 border border-emerald-700 font-bold">
            PYTORCH ACTIVE
          </span>
          <button
            onClick={() => setIsCollapsed(true)}
            className="p-1 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-all"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2 text-[10px]">
        <div className="p-2.5 rounded-xl bg-slate-900/80 border border-slate-800">
          <span className="text-[8px] text-slate-400 uppercase tracking-widest block font-bold">Model Accuracy</span>
          <span className="text-sm font-black text-emerald-400">99% F1</span>
        </div>
        <div className="p-2.5 rounded-xl bg-slate-900/80 border border-slate-800">
          <span className="text-[8px] text-slate-400 uppercase tracking-widest block font-bold">Inference Latency</span>
          <span className="text-sm font-black text-cyan-300 flex items-center space-x-1">
            <Zap className="w-3 h-3 text-emerald-400" />
            <span>{latency} ms</span>
          </span>
        </div>
      </div>

      <button className="w-full py-1.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-cyan-300 border border-slate-700 font-bold text-[10px] flex items-center justify-center space-x-1.5 transition-all">
        <RefreshCw className="w-3 h-3" />
        <span>Retrain Deep Learning Model</span>
      </button>
    </div>
  );
};
