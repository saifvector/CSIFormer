import React from 'react';
import { Brain, Activity, Zap, Building2, ShieldCheck } from 'lucide-react';
import type { ActivityPrediction } from '../../types/csi';

interface ZoneItem {
  name: string;
  is_restricted?: boolean;
  current_occupancy: number;
  entry_count: number;
  exit_count: number;
  avg_dwell_seconds: number;
  utilization_pct: number;
}

interface EventItem {
  id: string;
  type: string;
  severity: string;
  message: string;
  timestamp: number;
  time_str: string;
}

interface LeftIntelligenceRailProps {
  activity: ActivityPrediction | null;
  digitalTwin?: {
    zones?: ZoneItem[];
  } | null;
  events?: EventItem[] | null;
  insights?: {
    space_utilization_score_pct?: number;
    observations?: string[];
  } | null;
  onSelectActivity?: (activity: string) => void;
}

export const LeftIntelligenceRail: React.FC<LeftIntelligenceRailProps> = ({
  activity,
  digitalTwin,
  insights,
  onSelectActivity,
}) => {
  const currentActivity = activity?.activity || 'Walking';
  const confidence = Math.round((activity?.confidence || 0.985) * 100);

  const classes = [
    { label: 'Empty Room', key: 'Empty Room' },
    { label: 'Standing', key: 'Standing' },
    { label: 'Sitting', key: 'Sitting' },
    { label: 'Walking', key: 'Walking' },
    { label: 'Running', key: 'Running' },
    { label: 'Falling', key: 'Falling' },
    { label: 'Lying Down', key: 'Lying Down' },
    { label: 'Multiple Persons', key: 'Multiple Persons' },
  ];

  const zones = digitalTwin?.zones || [
    { name: 'Workspace Area', current_occupancy: 1, entry_count: 12, exit_count: 11, avg_dwell_seconds: 45.2, utilization_pct: 88.5 },
    { name: 'Meeting Area', current_occupancy: 0, entry_count: 4, exit_count: 4, avg_dwell_seconds: 22.0, utilization_pct: 35.0 },
    { name: 'Entrance Zone', current_occupancy: 0, entry_count: 14, exit_count: 14, avg_dwell_seconds: 8.5, utilization_pct: 42.0 },
    { name: 'Waiting Area', current_occupancy: 0, entry_count: 3, exit_count: 3, avg_dwell_seconds: 18.0, utilization_pct: 25.0 },
    { name: 'Restricted Area', is_restricted: true, current_occupancy: 0, entry_count: 0, exit_count: 0, avg_dwell_seconds: 0.0, utilization_pct: 0.0 },
    { name: 'Exit Zone', current_occupancy: 0, entry_count: 14, exit_count: 14, avg_dwell_seconds: 6.0, utilization_pct: 18.0 },
  ];

  const spaceScore = insights?.space_utilization_score_pct ?? 82.5;

  return (
    <div className="w-80 h-full bg-[#081120]/95 border-r border-[#00F0FF]/20 p-4 font-mono text-xs text-[#E2F8FF] space-y-4 overflow-y-auto pointer-events-auto shadow-2xl flex flex-col justify-between">
      <div className="space-y-4">
        {/* Section 1: Activity Intelligence */}
        <div className="space-y-2">
          <div className="flex items-center justify-between pb-1 border-b border-slate-800">
            <div className="flex items-center space-x-2 text-[#00F0FF]">
              <Brain className="w-4 h-4" />
              <h3 className="text-xs font-black uppercase tracking-widest text-[#E2F8FF]">Activity Intelligence</h3>
            </div>
            <span className="text-[9px] px-2 py-0.5 rounded bg-emerald-950 text-emerald-300 border border-emerald-700 font-bold">
              30 Hz CLASSIFIER
            </span>
          </div>

          <div className="p-3 rounded-xl bg-[#020617] border border-[#00F0FF]/30 flex items-center justify-between">
            <div>
              <span className="text-[9px] text-[#94A3B8] uppercase tracking-widest block font-bold">Target State</span>
              <span className="text-base font-extrabold text-[#00F0FF]">{currentActivity}</span>
            </div>
            <div className="text-right">
              <span className="text-[9px] text-[#94A3B8] uppercase tracking-widest block font-bold">Confidence</span>
              <span className="text-sm font-black text-emerald-400">{confidence}%</span>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-1.5 pt-1">
            {classes.map((cls) => {
              const isActive = currentActivity === cls.key;
              return (
                <button
                  key={cls.key}
                  onClick={() => onSelectActivity && onSelectActivity(cls.key)}
                  className={`p-2 rounded-lg text-left font-bold transition-all border text-[10px] ${
                    isActive
                      ? 'bg-[#00F0FF] text-slate-950 border-[#00F0FF] shadow-md shadow-[#00F0FF]/30'
                      : 'bg-[#020617] text-[#94A3B8] border-slate-800 hover:border-[#00F0FF]/40 hover:text-[#E2F8FF]'
                  }`}
                >
                  {cls.label}
                </button>
              );
            })}
          </div>
        </div>

        {/* Section 2: AI Model Health */}
        <div className="space-y-2 pt-2 border-t border-slate-800">
          <div className="flex items-center justify-between pb-1 border-b border-slate-800">
            <div className="flex items-center space-x-2 text-[#00F0FF]">
              <Activity className="w-4 h-4" />
              <h3 className="text-xs font-black uppercase tracking-widest text-[#E2F8FF]">CSIFormer AI Health</h3>
            </div>
            <span className="text-[9px] text-emerald-400 font-bold flex items-center space-x-1">
              <Zap className="w-3 h-3 text-emerald-400" />
              <span>PYTORCH GPU</span>
            </span>
          </div>

          <div className="grid grid-cols-2 gap-2 text-[10px]">
            <div className="p-2.5 rounded-xl bg-[#020617] border border-slate-800">
              <span className="text-[8px] text-[#94A3B8] uppercase tracking-widest block font-bold">Model Accuracy</span>
              <span className="text-sm font-black text-emerald-400">99% F1</span>
            </div>
            <div className="p-2.5 rounded-xl bg-[#020617] border border-slate-800">
              <span className="text-[8px] text-[#94A3B8] uppercase tracking-widest block font-bold">Inference Latency</span>
              <span className="text-sm font-black text-[#00F0FF]">8.2 ms</span>
            </div>
          </div>
        </div>

        {/* Section 3: Digital Twin Summary & 6 Semantic Zones */}
        <div className="space-y-2 pt-2 border-t border-slate-800">
          <div className="flex items-center justify-between pb-1 border-b border-slate-800">
            <div className="flex items-center space-x-2 text-[#00F0FF]">
              <Building2 className="w-4 h-4" />
              <h3 className="text-xs font-black uppercase tracking-widest text-[#E2F8FF]">Digital Twin Summary</h3>
            </div>
            <span className="text-[9px] text-[#00F0FF] font-bold">
              UTIL: {spaceScore}%
            </span>
          </div>

          <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
            {zones.map((zone) => (
              <div key={zone.name} className="p-2 rounded-xl bg-[#020617] border border-slate-800 text-[10px] space-y-1">
                <div className="flex justify-between font-bold">
                  <span className={zone.is_restricted ? 'text-rose-400' : 'text-[#E2F8FF]'}>{zone.name}</span>
                  <span className="text-[#00F0FF]">{zone.current_occupancy} Occ</span>
                </div>
                <div className="w-full bg-slate-900 h-1 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full ${zone.is_restricted ? 'bg-rose-500' : 'bg-[#00F0FF]'}`}
                    style={{ width: `${zone.utilization_pct}%` }}
                  ></div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Footer Branding */}
      <div className="pt-2 border-t border-slate-800 text-[9px] text-[#94A3B8] flex items-center justify-between">
        <span className="flex items-center space-x-1">
          <ShieldCheck className="w-3 h-3 text-[#00F0FF]" />
          <span>ISR Defense-Tech Engine</span>
        </span>
        <span className="font-bold text-[#00F0FF]">v2.5 PRO</span>
      </div>
    </div>
  );
};
