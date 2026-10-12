import React, { useState } from 'react';
import { Radio, Signal, ChevronRight, ChevronLeft } from 'lucide-react';
import type { NodeInfo } from '../../types/csi';

interface RightAnalyticsHUDProps {
  nodes: NodeInfo[];
  rssi?: number;
  snr?: number;
}

export const RightAnalyticsHUD: React.FC<RightAnalyticsHUDProps> = ({
  nodes,
  rssi = -52.0,
  snr = 34.5,
}) => {
  const [isCollapsed, setIsCollapsed] = useState<boolean>(false);

  if (isCollapsed) {
    return (
      <button
        onClick={() => setIsCollapsed(false)}
        className="absolute bottom-20 right-4 z-40 p-3 hud-panel hud-panel-cyan rounded-2xl font-mono text-cyan-400 hover:text-cyan-300 pointer-events-auto transition-all shadow-2xl flex items-center space-x-2 bg-slate-950/80 border border-slate-800"
      >
        <ChevronLeft className="w-4 h-4" />
        <Signal className="w-5 h-5" />
        <span className="text-xs font-bold uppercase tracking-wider text-slate-100">{rssi} dBm</span>
      </button>
    );
  }

  return (
    <div className="absolute bottom-20 right-4 z-40 w-72 hud-panel hud-panel-cyan rounded-2xl p-4 font-mono text-xs pointer-events-auto transition-all space-y-3 shadow-2xl bg-slate-950/90 border border-slate-800">
      {/* Header with Collapse Button */}
      <div className="flex items-center justify-between pb-2 border-b border-slate-800">
        <div className="flex items-center space-x-2 text-cyan-400">
          <Signal className="w-4 h-4" />
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-100">Wireless Physical Layer</h3>
        </div>
        <button
          onClick={() => setIsCollapsed(true)}
          className="p-1 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-all"
        >
          <ChevronRight className="w-4 h-4" />
        </button>
      </div>

      {/* Signal Strength & SNR */}
      <div className="grid grid-cols-2 gap-2 text-[10px]">
        <div className="p-2.5 rounded-xl bg-slate-900/80 border border-slate-800">
          <span className="text-[8px] text-slate-400 uppercase tracking-widest block font-bold">Signal (RSSI)</span>
          <span className="text-sm font-black text-cyan-300">{rssi} dBm</span>
        </div>
        <div className="p-2.5 rounded-xl bg-slate-900/80 border border-slate-800">
          <span className="text-[8px] text-slate-400 uppercase tracking-widest block font-bold">SNR Ratio</span>
          <span className="text-sm font-black text-emerald-400">{snr} dB</span>
        </div>
      </div>

      {/* Hardware Receiver Node Status List */}
      <div className="space-y-1.5 pt-1 text-[10px]">
        <span className="text-[9px] text-slate-400 font-bold uppercase block">Receiver Topology:</span>
        {nodes.map((n) => (
          <div key={n.id} className="p-2 rounded-xl bg-slate-900/60 border border-slate-800 flex items-center justify-between">
            <div className="flex items-center space-x-1.5">
              <Radio className="w-3 h-3 text-cyan-400" />
              <span className="text-slate-200 font-medium">{n.name}</span>
            </div>
            <span className="text-emerald-400 font-mono text-[9px] font-bold">30 Hz</span>
          </div>
        ))}
      </div>
    </div>
  );
};
