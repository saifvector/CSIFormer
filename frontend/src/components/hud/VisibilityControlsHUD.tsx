import React from 'react';
import { Sliders, Grid, Radio, Sparkles, Activity, User, Flame, RotateCw, ShieldCheck, Eye } from 'lucide-react';
import type { SpatialVisibilitySettings, RenderingMode } from '../../types/csi';

interface VisibilityControlsHUDProps {
  visibility: SpatialVisibilitySettings;
  setVisibility: React.Dispatch<React.SetStateAction<SpatialVisibilitySettings>>;
}

export const VisibilityControlsHUD: React.FC<VisibilityControlsHUDProps> = ({
  visibility,
  setVisibility
}) => {
  const currentMode = visibility.renderingMode || 'production';

  const setMode = (mode: RenderingMode) => {
    setVisibility((prev) => ({
      ...prev,
      renderingMode: mode,
      showPointCloud: mode !== 'production',
      showNavMesh: mode === 'debug',
    }));
  };

  const toggle = (key: keyof SpatialVisibilitySettings) => {
    if (key === 'renderingMode') return;
    setVisibility((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const controls = [
    { key: 'showGrid', label: 'Spatial Grid', icon: Grid },
    { key: 'showNodes', label: 'Sensor Nodes', icon: Radio },
    { key: 'showPointCloud', label: 'CSI Point Cloud', icon: Sparkles },
    { key: 'showBeams', label: 'RF Wave Beams', icon: Activity },
    { key: 'showAvatar', label: '3D Human Avatar', icon: User },
    { key: 'showTrajectory', label: 'Motion Ribbon', icon: Activity },
    { key: 'showHeatmap', label: 'Ground Heatmap', icon: Flame },
    { key: 'showNavMesh', label: 'NavMesh & Colliders', icon: ShieldCheck },
    { key: 'autoRotate', label: 'Auto Rotate', icon: RotateCw },
  ] as const;

  return (
    <div className="absolute top-20 right-4 z-40 w-56 hud-panel rounded-2xl p-3.5 font-mono text-xs pointer-events-auto transition-all space-y-3">
      {/* Rendering Mode Selector */}
      <div className="space-y-1.5 pb-2.5 border-b border-slate-800">
        <div className="flex items-center space-x-1.5 text-[#00F0FF]">
          <Eye className="w-3.5 h-3.5" />
          <span className="text-[10px] font-black uppercase tracking-wider text-slate-200">Perception Mode</span>
        </div>
        <div className="grid grid-cols-3 gap-1 bg-[#020617] p-1 rounded-xl border border-slate-800 text-[9px] font-bold">
          <button
            onClick={() => setMode('production')}
            className={`py-1 rounded-lg transition-all ${
              currentMode === 'production'
                ? 'bg-cyan-500 text-slate-950 font-black shadow-md shadow-cyan-500/20'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            PROD
          </button>
          <button
            onClick={() => setMode('research')}
            className={`py-1 rounded-lg transition-all ${
              currentMode === 'research'
                ? 'bg-cyan-500 text-slate-950 font-black shadow-md shadow-cyan-500/20'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            RESEARCH
          </button>
          <button
            onClick={() => setMode('debug')}
            className={`py-1 rounded-lg transition-all ${
              currentMode === 'debug'
                ? 'bg-cyan-500 text-slate-950 font-black shadow-md shadow-cyan-500/20'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            DEBUG
          </button>
        </div>
      </div>

      <div className="flex items-center space-x-2 text-cyan-400 mb-1.5 pb-1 border-b border-slate-800">
        <Sliders className="w-4 h-4" />
        <h3 className="text-[10px] font-bold uppercase tracking-wider text-slate-100">3D Scene Layers</h3>
      </div>

      <div className="space-y-1">
        {controls.map((ctrl) => {
          const Icon = ctrl.icon;
          const isActive = visibility[ctrl.key];

          return (
            <button
              key={ctrl.key}
              onClick={() => toggle(ctrl.key)}
              className={`w-full flex items-center justify-between p-1.5 rounded-lg font-semibold transition-all ${
                isActive
                  ? 'bg-cyan-500/15 text-cyan-300 border border-cyan-500/30'
                  : 'text-slate-400 hover:bg-slate-900 hover:text-slate-200 border border-transparent'
              }`}
            >
              <div className="flex items-center space-x-2">
                <Icon className={`w-3.5 h-3.5 ${isActive ? 'text-cyan-400' : 'text-slate-500'}`} />
                <span>{ctrl.label}</span>
              </div>
              <span className={`w-2 h-2 rounded-full ${isActive ? 'bg-cyan-400 shadow-sm shadow-cyan-400' : 'bg-slate-700'}`}></span>
            </button>
          );
        })}
      </div>
    </div>
  );
};
