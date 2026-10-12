import React, { useState } from 'react';
import { Building2, Layers, Lightbulb, AlertTriangle, History, Play, Pause, AlertOctagon, ChevronLeft, ChevronRight } from 'lucide-react';

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

interface DigitalTwinHUDProps {
  digitalTwin?: {
    zones?: ZoneItem[];
    status?: string;
  } | null;
  events?: EventItem[] | null;
  insights?: {
    space_utilization_score_pct?: number;
    most_used_zone?: string;
    least_used_zone?: string;
    peak_occupancy_time?: string;
    observations?: string[];
  } | null;
}

export const DigitalTwinHUD: React.FC<DigitalTwinHUDProps> = ({
  digitalTwin,
  events,
  insights
}) => {
  const [isCollapsed, setIsCollapsed] = useState<boolean>(false);
  const [activeTab, setActiveTab] = useState<'zones' | 'insights' | 'events' | 'replay'>('zones');
  const [isReplaying, setIsReplaying] = useState<boolean>(false);
  const [replayOffset, setReplayOffset] = useState<number>(0);

  const zones = digitalTwin?.zones || [
    { name: 'Workspace Area', current_occupancy: 1, entry_count: 12, exit_count: 11, avg_dwell_seconds: 45.2, utilization_pct: 88.5 },
    { name: 'Meeting Area', current_occupancy: 0, entry_count: 4, exit_count: 4, avg_dwell_seconds: 22.0, utilization_pct: 35.0 },
    { name: 'Entrance Zone', current_occupancy: 0, entry_count: 14, exit_count: 14, avg_dwell_seconds: 8.5, utilization_pct: 42.0 },
    { name: 'Waiting Area', current_occupancy: 0, entry_count: 3, exit_count: 3, avg_dwell_seconds: 18.0, utilization_pct: 25.0 },
    { name: 'Restricted Area', is_restricted: true, current_occupancy: 0, entry_count: 0, exit_count: 0, avg_dwell_seconds: 0.0, utilization_pct: 0.0 },
    { name: 'Exit Zone', current_occupancy: 0, entry_count: 14, exit_count: 14, avg_dwell_seconds: 6.0, utilization_pct: 18.0 },
  ];

  const eventList = events || [
    { id: '1', type: 'ROOM_OCCUPIED', severity: 'INFO', message: 'Target active in Workspace Area', timestamp: Date.now(), time_str: '14:22:10' }
  ];

  const score = insights?.space_utilization_score_pct ?? 82.5;
  const observations = insights?.observations || [
    'Workspace Area represents primary spatial activity hub (82.5% efficiency).',
    'Traffic flow remains fluid through Entrance Zone corridor.',
    'Restricted Area perimeter is secure.'
  ];

  if (isCollapsed) {
    return (
      <button
        onClick={() => setIsCollapsed(false)}
        className="absolute top-20 left-4 z-40 p-3 hud-panel hud-panel-cyan rounded-2xl font-mono text-cyan-400 hover:text-cyan-300 pointer-events-auto transition-all shadow-2xl flex items-center space-x-2 bg-slate-950/80 border border-slate-800"
      >
        <Building2 className="w-5 h-5" />
        <span className="text-xs font-bold uppercase tracking-wider text-slate-100">Digital Twin</span>
        <ChevronRight className="w-4 h-4" />
      </button>
    );
  }

  return (
    <div className="absolute top-20 left-4 z-40 w-80 hud-panel hud-panel-cyan rounded-2xl p-4 font-mono text-xs pointer-events-auto transition-all space-y-3 shadow-2xl bg-slate-950/90 border border-slate-800">
      {/* Header with Collapse Button */}
      <div className="flex items-center justify-between pb-2 border-b border-slate-800">
        <div className="flex items-center space-x-2 text-cyan-400">
          <Building2 className="w-4 h-4" />
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-100">Digital Twin Intelligence</h3>
        </div>
        <button
          onClick={() => setIsCollapsed(true)}
          className="p-1 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-all"
        >
          <ChevronLeft className="w-4 h-4" />
        </button>
      </div>

      {/* Navigation Tabs */}
      <div className="grid grid-cols-4 gap-1 p-1 bg-slate-900/90 rounded-xl border border-slate-800 text-[10px]">
        <button
          onClick={() => setActiveTab('zones')}
          className={`py-1 rounded-lg font-bold transition-all flex items-center justify-center space-x-1 ${
            activeTab === 'zones' ? 'bg-cyan-500 text-slate-950 shadow-md shadow-cyan-500/20' : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <Layers className="w-3 h-3" />
          <span>Zones</span>
        </button>

        <button
          onClick={() => setActiveTab('insights')}
          className={`py-1 rounded-lg font-bold transition-all flex items-center justify-center space-x-1 ${
            activeTab === 'insights' ? 'bg-cyan-500 text-slate-950 shadow-md shadow-cyan-500/20' : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <Lightbulb className="w-3 h-3" />
          <span>AI Score</span>
        </button>

        <button
          onClick={() => setActiveTab('events')}
          className={`py-1 rounded-lg font-bold transition-all flex items-center justify-center space-x-1 ${
            activeTab === 'events' ? 'bg-cyan-500 text-slate-950 shadow-md shadow-cyan-500/20' : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <AlertTriangle className="w-3 h-3" />
          <span>Alerts</span>
        </button>

        <button
          onClick={() => setActiveTab('replay')}
          className={`py-1 rounded-lg font-bold transition-all flex items-center justify-center space-x-1 ${
            activeTab === 'replay' ? 'bg-cyan-500 text-slate-950 shadow-md shadow-cyan-500/20' : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <History className="w-3 h-3" />
          <span>Replay</span>
        </button>
      </div>

      {/* Tab Content */}
      {activeTab === 'zones' && (
        <div className="space-y-1.5 max-h-56 overflow-y-auto pr-1">
          {zones.map((zone) => {
            const isRestricted = zone.is_restricted;
            const borderColor = isRestricted ? 'border-rose-600/60 bg-rose-950/20' : 'border-slate-800 bg-slate-900/70';

            return (
              <div key={zone.name} className={`p-2 rounded-xl border ${borderColor} space-y-1 text-[10px]`}>
                <div className="flex items-center justify-between font-bold">
                  <div className="flex items-center space-x-1.5">
                    {isRestricted && <AlertOctagon className="w-3.5 h-3.5 text-rose-400 animate-pulse" />}
                    <span className={isRestricted ? 'text-rose-300' : 'text-slate-100'}>{zone.name}</span>
                  </div>
                  <span className="text-cyan-300 bg-slate-800 px-1.5 py-0.5 rounded text-[9px]">
                    {zone.current_occupancy} Occupant{zone.current_occupancy === 1 ? '' : 's'}
                  </span>
                </div>

                <div className="flex justify-between text-[9px] text-slate-400">
                  <span>Entries: {zone.entry_count}</span>
                  <span>Avg Dwell: {zone.avg_dwell_seconds}s</span>
                  <span className="font-bold text-emerald-400">{zone.utilization_pct}% Util</span>
                </div>

                <div className="w-full bg-slate-800 h-1 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full ${isRestricted ? 'bg-rose-500' : 'bg-gradient-to-r from-cyan-500 to-indigo-400'}`}
                    style={{ width: `${zone.utilization_pct}%` }}
                  ></div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {activeTab === 'insights' && (
        <div className="space-y-2.5">
          <div className="p-3 rounded-xl bg-slate-900/80 border border-slate-800 text-center">
            <span className="text-[9px] text-slate-400 uppercase tracking-widest block font-bold mb-1">
              Space Utilization Score
            </span>
            <div className="text-2xl font-black bg-gradient-to-r from-cyan-400 to-emerald-400 bg-clip-text text-transparent">
              {score}%
            </div>
            <div className="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden mt-1.5">
              <div
                className="bg-gradient-to-r from-cyan-500 to-emerald-400 h-full rounded-full"
                style={{ width: `${score}%` }}
              ></div>
            </div>
          </div>

          <div className="p-2.5 rounded-xl bg-slate-900/80 border border-slate-800 space-y-1 text-[10px]">
            <span className="text-[9px] text-cyan-400 font-bold uppercase tracking-wider block">
              AI Spatial Observations:
            </span>
            <ul className="space-y-1 text-slate-300">
              {observations.map((obs, idx) => (
                <li key={idx} className="flex items-start space-x-1.5">
                  <span className="text-cyan-400 font-bold">•</span>
                  <span>{obs}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {activeTab === 'events' && (
        <div className="space-y-1.5 max-h-56 overflow-y-auto pr-1">
          {eventList.map((evt) => {
            const isCrit = evt.severity === 'CRITICAL';
            const isWarn = evt.severity === 'WARNING';
            const badgeColor = isCrit ? 'bg-rose-950 text-rose-300 border-rose-700' : isWarn ? 'bg-amber-950 text-amber-300 border-amber-700' : 'bg-slate-800 text-cyan-300 border-slate-700';

            return (
              <div key={evt.id || evt.timestamp} className={`p-2 rounded-xl bg-slate-900/90 border ${isCrit ? 'border-rose-600/80' : 'border-slate-800'} space-y-1 text-[10px]`}>
                <div className="flex items-center justify-between">
                  <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold border ${badgeColor}`}>
                    {evt.type}
                  </span>
                  <span className="text-slate-400 text-[9px] font-mono">{evt.time_str}</span>
                </div>
                <p className="text-slate-200 font-medium text-[10px]">{evt.message}</p>
              </div>
            );
          })}
        </div>
      )}

      {activeTab === 'replay' && (
        <div className="p-3 rounded-xl bg-slate-900/90 border border-slate-800 space-y-2.5 text-[10px]">
          <div className="flex items-center justify-between font-bold text-cyan-400">
            <span>Historical Timeline Replay</span>
            <span className="text-slate-300">{replayOffset}s Ago</span>
          </div>

          <div className="flex items-center space-x-2">
            <button
              onClick={() => setIsReplaying(!isReplaying)}
              className="p-2 rounded-lg bg-cyan-500 text-slate-950 font-bold transition-all hover:bg-cyan-400"
            >
              {isReplaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
            </button>
            <input
              type="range"
              min={0}
              max={600}
              step={10}
              value={replayOffset}
              onChange={(e) => setReplayOffset(Number(e.target.value))}
              className="w-full accent-cyan-400"
            />
          </div>
        </div>
      )}
    </div>
  );
};
