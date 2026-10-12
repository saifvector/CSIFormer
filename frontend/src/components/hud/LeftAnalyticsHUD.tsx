import React, { useState } from 'react';
import { Brain, ChevronLeft, ChevronRight } from 'lucide-react';
import type { ActivityPrediction } from '../../types/csi';

interface LeftAnalyticsHUDProps {
  activity: ActivityPrediction | null;
  onSelectActivity?: (activity: string) => void;
}

export const LeftAnalyticsHUD: React.FC<LeftAnalyticsHUDProps> = ({
  activity,
  onSelectActivity,
}) => {
  const [isCollapsed, setIsCollapsed] = useState<boolean>(false);

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

  const currentActivity = activity?.activity || 'Walking';
  const confidence = Math.round((activity?.confidence || 0.985) * 100);

  if (isCollapsed) {
    return (
      <button
        onClick={() => setIsCollapsed(false)}
        className="absolute bottom-20 left-4 z-40 p-3 hud-panel hud-panel-cyan rounded-2xl font-mono text-cyan-400 hover:text-cyan-300 pointer-events-auto transition-all shadow-2xl flex items-center space-x-2 bg-slate-950/80 border border-slate-800"
      >
        <Brain className="w-5 h-5" />
        <span className="text-xs font-bold uppercase tracking-wider text-slate-100">{currentActivity} ({confidence}%)</span>
        <ChevronRight className="w-4 h-4" />
      </button>
    );
  }

  return (
    <div className="absolute bottom-20 left-4 z-40 w-72 hud-panel hud-panel-cyan rounded-2xl p-4 font-mono text-xs pointer-events-auto transition-all space-y-3 shadow-2xl bg-slate-950/90 border border-slate-800">
      {/* Header with Collapse Button */}
      <div className="flex items-center justify-between pb-2 border-b border-slate-800">
        <div className="flex items-center space-x-2 text-cyan-400">
          <Brain className="w-4 h-4" />
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-100">AI Activity Classifier</h3>
        </div>
        <button
          onClick={() => setIsCollapsed(true)}
          className="p-1 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-all"
        >
          <ChevronLeft className="w-4 h-4" />
        </button>
      </div>

      {/* Active Activity Card */}
      <div className="p-3 rounded-xl bg-slate-900/80 border border-slate-800 flex items-center justify-between">
        <div>
          <span className="text-[9px] text-slate-400 uppercase tracking-widest block font-bold">Detected Activity</span>
          <span className="text-base font-extrabold text-cyan-300">{currentActivity}</span>
        </div>
        <div className="text-right">
          <span className="text-[9px] text-slate-400 uppercase tracking-widest block font-bold">Confidence</span>
          <span className="text-sm font-black text-emerald-400">{confidence}%</span>
        </div>
      </div>

      {/* 8-Class Selection Grid */}
      <div className="grid grid-cols-2 gap-1.5 pt-1">
        {classes.map((cls) => {
          const isActive = currentActivity === cls.key;
          return (
            <button
              key={cls.key}
              onClick={() => onSelectActivity && onSelectActivity(cls.key)}
              className={`p-2 rounded-xl text-left font-bold transition-all border text-[10px] ${
                isActive
                  ? 'bg-cyan-500 text-slate-950 border-cyan-400 shadow-md shadow-cyan-500/20'
                  : 'bg-slate-900/60 text-slate-300 border-slate-800 hover:border-slate-700'
              }`}
            >
              {cls.label}
            </button>
          );
        })}
      </div>
    </div>
  );
};
