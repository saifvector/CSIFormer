import React from 'react';
import { Cpu, AlertOctagon, Footprints, Armchair, PersonStanding, UserCheck, AlertTriangle } from 'lucide-react';
import type { ActivityPrediction } from '../../types/csi';

interface SensingActivityHUDProps {
  activity: ActivityPrediction | null;
  onSelectActivity: (act: string) => void;
}

export const SensingActivityHUD: React.FC<SensingActivityHUDProps> = ({
  activity,
  onSelectActivity
}) => {
  const currentAct = activity?.activity || 'Walking';
  const confPct = Math.round((activity?.confidence || 0.96) * 100);

  const actBadges: Record<string, { icon: any; color: string }> = {
    Empty: { icon: UserCheck, color: 'text-slate-400' },
    Walking: { icon: Footprints, color: 'text-cyan-400' },
    Sitting: { icon: Armchair, color: 'text-indigo-400' },
    Standing: { icon: PersonStanding, color: 'text-emerald-400' },
    Falling: { icon: AlertOctagon, color: 'text-rose-400' },
  };

  const currentBadge = actBadges[currentAct] || actBadges['Walking'];
  const BadgeIcon = currentBadge.icon;

  const activities = ['Empty', 'Walking', 'Sitting', 'Standing', 'Falling'];

  return (
    <div className={`absolute bottom-6 right-6 z-40 w-84 hud-panel ${
      currentAct === 'Falling' ? 'hud-panel-rose animate-pulse' : 'hud-panel-cyan'
    } rounded-2xl p-4 font-mono pointer-events-auto transition-all`}>
      {/* Fall Alert Banner */}
      {activity?.anomaly_detected && (
        <div className="mb-3 p-2.5 rounded-xl bg-rose-950/90 border border-rose-600 text-rose-200 flex items-center space-x-2 text-xs font-bold animate-bounce shadow-lg shadow-rose-900/50">
          <AlertTriangle className="w-4 h-4 text-rose-400 flex-shrink-0" />
          <span>FALL DETECTED — TRANSIENT IMPACT WAVE</span>
        </div>
      )}

      <div className="flex items-center justify-between mb-3 border-b border-slate-800 pb-2">
        <div className="flex items-center space-x-2 text-cyan-400">
          <Cpu className="w-4 h-4" />
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-100">AI Perception State</h3>
        </div>
        <span className="text-[10px] px-2 py-0.5 rounded bg-slate-800 text-cyan-400 font-bold border border-slate-700">
          CONF: {confPct}%
        </span>
      </div>

      {/* Main Activity State Badge */}
      <div className="flex items-center justify-between p-3 rounded-xl bg-slate-900/80 border border-slate-800 mb-3">
        <div className="flex items-center space-x-3">
          <div className="p-2.5 rounded-xl bg-slate-800/80 border border-slate-700">
            <BadgeIcon className={`w-6 h-6 ${currentBadge.color}`} />
          </div>
          <div>
            <span className="text-[9px] text-slate-400 uppercase tracking-widest block">Predicted State</span>
            <h2 className={`text-xl font-black ${currentBadge.color} tracking-wide`}>
              {currentAct}
            </h2>
          </div>
        </div>

        {/* Confidence Dial Bar */}
        <div className="w-24">
          <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
            <div
              className="bg-gradient-to-r from-cyan-500 to-indigo-500 h-full rounded-full transition-all"
              style={{ width: `${confPct}%` }}
            ></div>
          </div>
          <span className="text-[10px] text-slate-400 text-right block mt-1 font-bold">{confPct}% Match</span>
        </div>
      </div>

      {/* Simulation Activity Injector */}
      <div>
        <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-1.5">
          Simulate Human Activity State:
        </span>
        <div className="flex flex-wrap gap-1">
          {activities.map((act) => (
            <button
              key={act}
              onClick={() => onSelectActivity(act)}
              className={`px-2.5 py-1 rounded-lg text-xs font-bold transition-all ${
                currentAct === act
                  ? 'bg-cyan-500 text-slate-950 shadow-md shadow-cyan-500/20'
                  : 'bg-slate-900 text-slate-300 hover:bg-slate-800 border border-slate-800'
              }`}
            >
              {act}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
};
