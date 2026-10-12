import React from 'react';
import { Users, UserCheck, Activity, Navigation } from 'lucide-react';

interface SingleTrackInfo {
  track_id: string;
  color: string;
  x: number;
  y: number;
  z: number;
  speed_ms: number;
  activity: string;
  zone: string;
}

interface MultiTargetHUDProps {
  multiperson?: {
    person_count?: number;
    occupancy_status?: string;
    crowd_density_pct?: number;
    detection_confidence?: number;
    tracks?: SingleTrackInfo[];
  } | null;
}

export const MultiTargetHUD: React.FC<MultiTargetHUDProps> = ({ multiperson }) => {
  const count = multiperson?.person_count ?? 1;
  const status = multiperson?.occupancy_status || 'Occupied Room';
  const density = multiperson?.crowd_density_pct ?? 25.0;
  const tracks = multiperson?.tracks || [
    {
      track_id: 'Track-001',
      color: '#00F0FF',
      x: 4.18,
      y: 2.50,
      z: 1.10,
      speed_ms: 0.85,
      activity: 'Walking',
      zone: 'Workspace Area'
    }
  ];

  return (
    <div className="absolute top-84 right-4 z-40 w-76 hud-panel hud-panel-cyan rounded-2xl p-3.5 font-mono text-xs pointer-events-auto transition-all space-y-2.5">
      {/* Header */}
      <div className="flex items-center justify-between pb-1.5 border-b border-slate-800">
        <div className="flex items-center space-x-2 text-cyan-400">
          <Users className="w-4 h-4" />
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-100">Multi-Person Tracking</h3>
        </div>
        <div className="flex items-center space-x-1 px-2 py-0.5 rounded bg-emerald-950 text-emerald-300 border border-emerald-700 text-[10px] font-bold">
          <UserCheck className="w-3 h-3 text-emerald-400" />
          <span>{count} {count === 1 ? 'Person' : 'Persons'} Active</span>
        </div>
      </div>

      {/* Occupancy & Crowd Density Index */}
      <div className="p-2 rounded-xl bg-slate-900/80 border border-slate-800 space-y-1 text-[10px]">
        <div className="flex justify-between items-center font-bold">
          <span className="text-slate-400">Occupancy Status:</span>
          <span className="text-emerald-400">{status}</span>
        </div>
        <div className="flex justify-between items-center font-bold">
          <span className="text-slate-400">Crowd Density Index:</span>
          <span className="text-cyan-300">{density}%</span>
        </div>
        <div className="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden">
          <div
            className="bg-gradient-to-r from-cyan-500 via-amber-500 to-rose-500 h-full rounded-full transition-all"
            style={{ width: `${density}%` }}
          ></div>
        </div>
      </div>

      {/* Per-Target Active Tracking List */}
      <div className="space-y-1.5">
        <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
          Persistent Track Identities ({tracks.length}):
        </span>

        <div className="space-y-1.5 max-h-44 overflow-y-auto pr-1">
          {tracks.map((track) => (
            <div
              key={track.track_id}
              className="p-2 rounded-xl bg-slate-900/90 border border-slate-800 space-y-1 text-[10px]"
            >
              <div className="flex items-center justify-between font-bold">
                <div className="flex items-center space-x-1.5">
                  <span
                    className="w-2.5 h-2.5 rounded-full shadow-md"
                    style={{ backgroundColor: track.color }}
                  ></span>
                  <span className="text-slate-100">{track.track_id}</span>
                </div>
                <span
                  className="px-1.5 py-0.5 rounded text-[9px] font-extrabold uppercase border"
                  style={{ color: track.color, borderColor: track.color + '60', backgroundColor: track.color + '15' }}
                >
                  {track.activity}
                </span>
              </div>

              <div className="flex items-center justify-between text-slate-400 text-[9px]">
                <div className="flex items-center space-x-1">
                  <Navigation className="w-3 h-3 text-cyan-400" />
                  <span>({track.x.toFixed(2)}m, {track.y.toFixed(2)}m)</span>
                </div>
                <div className="flex items-center space-x-1 text-slate-300">
                  <Activity className="w-3 h-3 text-amber-400" />
                  <span>{track.speed_ms.toFixed(2)} m/s</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
