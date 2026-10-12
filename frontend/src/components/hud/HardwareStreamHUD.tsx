import React, { useState } from 'react';
import { Cpu, Usb, Wifi, CheckCircle2 } from 'lucide-react';
import { setHardwareSource } from '../../services/api';

interface HardwareStreamHUDProps {
  activeMode?: string;
  hardwareConnected?: boolean;
  rssi?: number;
  snr?: number;
  packetRate?: number;
}

export const HardwareStreamHUD: React.FC<HardwareStreamHUDProps> = ({
  activeMode = 'simulated',
  hardwareConnected = false,
  rssi = -52.0,
  snr = 34.5,
  packetRate = 30
}) => {
  const [currentMode, setCurrentMode] = useState<string>(activeMode);
  const [isOpen, setIsOpen] = useState<boolean>(false);

  const handleSelectMode = async (mode: string) => {
    setCurrentMode(mode);
    try {
      await setHardwareSource(mode);
    } catch (err) {
      console.error('Failed to set hardware source:', err);
    }
  };

  const sources = [
    { id: 'simulated', name: 'Physics Simulator', icon: Cpu, desc: '64 Subcarrier Multipath Physics' },
    { id: 'esp32_serial', name: 'ESP32-S3 USB Serial', icon: Usb, desc: '921.6k Baud COM3 Stream' },
    { id: 'esp32_udp', name: 'ESP32-S3 UDP Broadcast', icon: Wifi, desc: 'Port 5555 Wi-Fi Packet Listener' }
  ];

  return (
    <div className="absolute top-20 left-4 z-40 w-64 hud-panel hud-panel-cyan rounded-2xl p-3.5 font-mono text-xs pointer-events-auto transition-all">
      <div className="flex items-center justify-between mb-2 pb-1.5 border-b border-slate-800">
        <div className="flex items-center space-x-2 text-cyan-400">
          <Cpu className="w-4 h-4" />
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-100">CSI Hardware Driver</h3>
        </div>
        <div className="flex items-center space-x-1.5">
          <span className={`w-2 h-2 rounded-full ${hardwareConnected ? 'bg-emerald-400' : 'bg-amber-400'}`}></span>
          <button
            onClick={() => setIsOpen(!isOpen)}
            className="text-[10px] text-cyan-300 hover:text-cyan-100 font-bold px-1.5 py-0.5 rounded bg-slate-800 border border-slate-700"
          >
            {isOpen ? 'Close' : 'Switch Source'}
          </button>
        </div>
      </div>

      {isOpen ? (
        <div className="space-y-1.5 my-2">
          {sources.map((src) => {
            const Icon = src.icon;
            const isSelected = currentMode === src.id;
            return (
              <button
                key={src.id}
                onClick={() => handleSelectMode(src.id)}
                className={`w-full flex items-center justify-between p-2 rounded-xl border text-left transition-all ${
                  isSelected
                    ? 'bg-cyan-950/60 border-cyan-500/80 text-cyan-300'
                    : 'bg-slate-900/60 border-slate-800 text-slate-400 hover:border-slate-700'
                }`}
              >
                <div className="flex items-center space-x-2">
                  <Icon className="w-3.5 h-3.5 text-cyan-400" />
                  <div>
                    <h4 className="text-[11px] font-bold text-slate-200">{src.name}</h4>
                    <span className="text-[9px] text-slate-400 block">{src.desc}</span>
                  </div>
                </div>
                {isSelected && <CheckCircle2 className="w-3.5 h-3.5 text-cyan-400" />}
              </button>
            );
          })}
        </div>
      ) : (
        <div className="space-y-1.5">
          <div className="flex items-center justify-between p-2 rounded-xl bg-slate-900/60 border border-slate-800">
            <span className="text-slate-400 text-[10px] uppercase">Active Source:</span>
            <span className="text-cyan-400 font-bold text-[11px] uppercase">
              {currentMode === 'simulated' ? 'Physics Sim' : currentMode.toUpperCase()}
            </span>
          </div>

          <div className="grid grid-cols-2 gap-2 text-center text-[10px]">
            <div className="bg-slate-900/60 p-1.5 rounded-xl border border-slate-800">
              <span className="text-slate-500 block">Packet Rate</span>
              <span className="text-emerald-400 font-bold text-xs">{packetRate} Hz</span>
            </div>
            <div className="bg-slate-900/60 p-1.5 rounded-xl border border-slate-800">
              <span className="text-slate-500 block">RSSI / SNR</span>
              <span className="text-cyan-300 font-bold text-xs">{rssi} / {snr} dB</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
