import React, { useState } from 'react';
import { Cpu, Activity, Radio, Server, ChevronRight, ChevronLeft } from 'lucide-react';

interface DeviceItem {
  device_id: string;
  name: string;
  mac: string;
  port: string;
  status: string;
  firmware_version: string;
  packets_received: number;
  packet_loss_pct: number;
  packet_rate_hz: number;
  rssi: number;
  noise_floor: number;
  snr: number;
  subcarriers_count: number;
}

interface HardwareControlHUDProps {
  hardware?: {
    acquisition_mode?: string;
    connected_device_count?: number;
    total_packet_rate_hz?: number;
    average_rssi?: number;
    devices?: DeviceItem[];
  } | null;
  subcarriers?: {
    amplitudes?: number[];
    phases?: number[];
  } | null;
}

export const HardwareControlHUD: React.FC<HardwareControlHUDProps> = ({
  hardware,
  subcarriers
}) => {
  const [isCollapsed, setIsCollapsed] = useState<boolean>(false);
  const [selectedDevice, setSelectedDevice] = useState<string>('esp32-rx-01');
  const [viewMode, setViewMode] = useState<'devices' | 'subcarriers'>('devices');

  const devices = hardware?.devices || [
    { device_id: 'esp32-rx-01', name: 'ESP32-S3 RX West', mac: '24:DC:C3:A1:01:01', port: 'COM3 (USB Serial)', status: 'connected', firmware_version: 'ESP-IDF v5.1.2', packets_received: 4820, packet_loss_pct: 0.12, packet_rate_hz: 30.0, rssi: -52.0, noise_floor: -95.0, snr: 43.0, subcarriers_count: 64 },
    { device_id: 'esp32-rx-02', name: 'ESP32-S3 RX East', mac: '24:DC:C3:A1:01:02', port: 'COM4 (USB Serial)', status: 'connected', firmware_version: 'ESP-IDF v5.1.2', packets_received: 4818, packet_loss_pct: 0.15, packet_rate_hz: 30.0, rssi: -54.5, noise_floor: -95.0, snr: 40.5, subcarriers_count: 64 },
    { device_id: 'esp32-rx-03', name: 'ESP32-S3 RX South', mac: '24:DC:C3:A1:01:03', port: 'Port 5555 (UDP)', status: 'connected', firmware_version: 'ESP-IDF v5.1.2', packets_received: 4825, packet_loss_pct: 0.08, packet_rate_hz: 30.0, rssi: -51.2, noise_floor: -95.0, snr: 43.8, subcarriers_count: 64 }
  ];

  const amps = subcarriers?.amplitudes || Array.from({ length: 64 }, (_, i) => 15.0 + Math.sin(i * 0.2) * 4.0);

  if (isCollapsed) {
    return (
      <button
        onClick={() => setIsCollapsed(false)}
        className="absolute top-20 right-4 z-40 p-3 hud-panel hud-panel-cyan rounded-2xl font-mono text-cyan-400 hover:text-cyan-300 pointer-events-auto transition-all shadow-2xl flex items-center space-x-2 bg-slate-950/80 border border-slate-800"
      >
        <ChevronLeft className="w-4 h-4" />
        <Cpu className="w-5 h-5" />
        <span className="text-xs font-bold uppercase tracking-wider text-slate-100">ESP32 Hardware</span>
      </button>
    );
  }

  return (
    <div className="absolute top-20 right-4 z-40 w-84 hud-panel hud-panel-cyan rounded-2xl p-4 font-mono text-xs pointer-events-auto space-y-3 shadow-2xl bg-slate-950/90 border border-slate-800">
      {/* Header */}
      <div className="flex items-center justify-between pb-2 border-b border-slate-800">
        <div className="flex items-center space-x-2 text-cyan-400">
          <Cpu className="w-4 h-4" />
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-100">ESP32 Hardware Control</h3>
        </div>
        <button
          onClick={() => setIsCollapsed(true)}
          className="p-1 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-all"
        >
          <ChevronRight className="w-4 h-4" />
        </button>
      </div>

      {/* Mode Selector */}
      <div className="grid grid-cols-2 gap-1 p-1 bg-slate-900/90 rounded-xl border border-slate-800 text-[10px]">
        <button
          onClick={() => setViewMode('devices')}
          className={`py-1 rounded-lg font-bold transition-all flex items-center justify-center space-x-1 ${
            viewMode === 'devices' ? 'bg-cyan-500 text-slate-950 shadow-md shadow-cyan-500/20' : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <Server className="w-3 h-3" />
          <span>Active RX Nodes ({devices.length})</span>
        </button>

        <button
          onClick={() => setViewMode('subcarriers')}
          className={`py-1 rounded-lg font-bold transition-all flex items-center justify-center space-x-1 ${
            viewMode === 'subcarriers' ? 'bg-cyan-500 text-slate-950 shadow-md shadow-cyan-500/20' : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <Activity className="w-3 h-3" />
          <span>64 Subcarrier Signal</span>
        </button>
      </div>

      {/* Mode 1: Active ESP32-S3 RX Devices */}
      {viewMode === 'devices' && (
        <div className="space-y-2 max-h-60 overflow-y-auto pr-1">
          {devices.map((dev) => (
            <div
              key={dev.device_id}
              onClick={() => setSelectedDevice(dev.device_id)}
              className={`p-2.5 rounded-xl border transition-all cursor-pointer ${
                selectedDevice === dev.device_id ? 'border-cyan-500 bg-slate-900/90 shadow-lg shadow-cyan-500/10' : 'border-slate-800 bg-slate-900/60 hover:border-slate-700'
              }`}
            >
              <div className="flex items-center justify-between font-bold text-[10px]">
                <div className="flex items-center space-x-1.5 text-slate-100">
                  <Radio className="w-3.5 h-3.5 text-cyan-400" />
                  <span>{dev.name}</span>
                </div>
                <span className="text-[9px] px-1.5 py-0.5 rounded bg-slate-800 text-cyan-300 border border-slate-700">
                  {dev.port}
                </span>
              </div>

              <div className="grid grid-cols-3 gap-1 mt-1.5 text-[9px] text-slate-400">
                <div>
                  <span className="block text-[8px] text-slate-500">PACKET RATE</span>
                  <span className="font-bold text-emerald-400">{dev.packet_rate_hz} Hz</span>
                </div>
                <div>
                  <span className="block text-[8px] text-slate-500">SIGNAL (RSSI)</span>
                  <span className="font-bold text-cyan-300">{dev.rssi} dBm</span>
                </div>
                <div>
                  <span className="block text-[8px] text-slate-500">PACKET LOSS</span>
                  <span className="font-bold text-slate-200">{dev.packet_loss_pct}%</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Mode 2: Live 64 Subcarrier Signal Inspector */}
      {viewMode === 'subcarriers' && (
        <div className="p-3 rounded-xl bg-slate-900/90 border border-slate-800 space-y-2">
          <div className="flex items-center justify-between text-[10px] font-bold text-cyan-400">
            <span>64 Subcarrier Amplitude Profile</span>
            <span className="text-slate-400 text-[9px]">64 SC @ 20 MHz</span>
          </div>

          <div className="h-24 w-full flex items-end justify-between gap-[1px] bg-slate-950 p-2 rounded-lg border border-slate-800">
            {amps.map((amp, idx) => {
              const heightPct = Math.min(100, Math.max(10, (amp / 30.0) * 100));
              return (
                <div
                  key={idx}
                  className="w-full bg-cyan-400/80 hover:bg-cyan-300 rounded-t-sm transition-all"
                  style={{ height: `${heightPct}%` }}
                  title={`Subcarrier ${idx + 1}: ${amp.toFixed(1)} dB`}
                ></div>
              );
            })}
          </div>

          <div className="flex justify-between text-[9px] text-slate-500 font-mono">
            <span>SC-01 (2.412 GHz)</span>
            <span>SC-32 (Center)</span>
            <span>SC-64 (2.432 GHz)</span>
          </div>
        </div>
      )}
    </div>
  );
};
