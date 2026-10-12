import React, { useState } from 'react';
import { FlaskConical, Play, Square } from 'lucide-react';
import { startExperiment, stopExperiment } from '../../services/api';

interface ExperimentManagerHUDProps {
  experimentStatus?: {
    status?: string;
    title?: string;
    elapsed_sec?: number;
    target_duration_sec?: number;
    samples_collected?: number;
  } | null;
}

export const ExperimentManagerHUD: React.FC<ExperimentManagerHUDProps> = ({
  experimentStatus
}) => {
  const [selectedExp, setSelectedExp] = useState<string>('exp_01');
  const [isRecording, setIsRecording] = useState<boolean>(false);

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
    <div className="absolute bottom-24 right-4 z-40 w-84 hud-panel hud-panel-cyan rounded-2xl p-3.5 font-mono text-xs pointer-events-auto space-y-2.5 shadow-2xl">
      <div className="flex items-center justify-between pb-1.5 border-b border-slate-800">
        <div className="flex items-center space-x-2 text-cyan-400">
          <FlaskConical className="w-4 h-4" />
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-100">Experiment Protocol Manager</h3>
        </div>
        <span className={`text-[9px] px-2 py-0.5 rounded font-bold border ${isExpActive ? 'bg-rose-950 text-rose-300 border-rose-700 animate-pulse' : 'bg-slate-800 text-slate-400 border-slate-700'}`}>
          {isExpActive ? 'RECORDING' : 'IDLE'}
        </span>
      </div>

      <div className="space-y-1.5 text-[10px]">
        <label className="text-[9px] text-slate-400 font-bold uppercase block">Select Protocol:</label>
        <select
          value={selectedExp}
          onChange={(e) => setSelectedExp(e.target.value)}
          disabled={isExpActive}
          className="w-full bg-slate-900 border border-slate-700 text-slate-200 rounded-lg p-1.5 text-[10px] focus:outline-none focus:border-cyan-500 font-mono"
        >
          <option value="exp_01">Exp 01: Empty Room Baseline (60s)</option>
          <option value="exp_02">Exp 02: Static Postures (Standing vs Sitting) (120s)</option>
          <option value="exp_03">Exp 03: Dynamic Motion (Walking/Running/Falling) (180s)</option>
          <option value="exp_04">Exp 04: Multi-Person Spatial Tracking (240s)</option>
        </select>
      </div>

      <div className="flex items-center justify-between gap-2 pt-1">
        {!isExpActive ? (
          <button
            onClick={handleStart}
            className="w-full py-2 rounded-xl bg-gradient-to-r from-cyan-500 to-emerald-400 text-slate-950 font-extrabold flex items-center justify-center space-x-1.5 shadow-lg shadow-cyan-500/20 hover:brightness-110 transition-all"
          >
            <Play className="w-3.5 h-3.5 fill-current" />
            <span>Launch Experiment Protocol</span>
          </button>
        ) : (
          <button
            onClick={handleStop}
            className="w-full py-2 rounded-xl bg-rose-600 hover:bg-rose-500 text-white font-extrabold flex items-center justify-center space-x-1.5 shadow-lg shadow-rose-600/20 transition-all"
          >
            <Square className="w-3.5 h-3.5 fill-current" />
            <span>Stop & Export Experiment Data</span>
          </button>
        )}
      </div>
    </div>
  );
};
