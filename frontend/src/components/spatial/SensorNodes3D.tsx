import React, { useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import { Html } from '@react-three/drei';
import * as THREE from 'three';
import type { NodeInfo, TargetPosition3D } from '../../types/csi';

interface SensorNodes3DProps {
  nodes: NodeInfo[];
  target?: TargetPosition3D | null;
  showBeams?: boolean;
}

// ═══════════════════════════════════════════════════════════════
// SENSOR TOPOLOGY — Realistic Wi-Fi Router + 3x ESP32-S3 Receivers
// ═══════════════════════════════════════════════════════════════

export const SensorNodes3D: React.FC<SensorNodes3DProps> = ({ nodes }) => {
  const routerPulseRef = useRef<THREE.Group>(null);
  const rxGlowRefs = useRef<(THREE.Mesh | null)[]>([]);

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime();

    // Router beacon wave pulses
    if (routerPulseRef.current) {
      routerPulseRef.current.children.forEach((child, idx) => {
        const scale = 0.2 + ((t * 1.2 + idx * 0.6) % 2.0);
        child.scale.set(scale, scale, scale);
        const mat = (child as THREE.Mesh).material as THREE.MeshBasicMaterial;
        if (mat) mat.opacity = Math.max(0, 0.45 * (1.0 - scale / 2.0));
      });
    }

    // ESP32 reception LED blink
    rxGlowRefs.current.forEach((mesh) => {
      if (mesh) {
        const mat = mesh.material as THREE.MeshStandardMaterial;
        if (mat) mat.emissiveIntensity = 2.5 + Math.sin(t * 4.0) * 1.0;
      }
    });
  });

  // Map room coords to 3D — ESP32 RX nodes go to FLOOR level (y=0)
  // since they are on tripod stands (tripod handles local height)
  const mapTo3D = (x: number, y: number, _z: number): [number, number, number] => {
    return [x - 5.0, 0, y - 4.0];
  };

  // Router ON the desk — desk is at [-1.8, 0, 1.5] in 3D, surface at y=0.76
  const routerPos: [number, number, number] = [-2.3, 0.76, 1.2];

  return (
    <group>
      {/* ══════════════════════════════════════════════════════════
          WI-FI 6 ROUTER — 25cm x 5cm x 16cm, sitting on desk
         ══════════════════════════════════════════════════════════ */}
      <group position={routerPos}>
        {/* Router chassis */}
        <mesh position={[0, 0.025, 0]}>
          <boxGeometry args={[0.25, 0.05, 0.16]} />
          <meshStandardMaterial color="#1E293B" roughness={0.25} metalness={0.85} />
        </mesh>

        {/* Front LED bar */}
        <mesh position={[0, 0.051, 0.075]}>
          <boxGeometry args={[0.14, 0.006, 0.004]} />
          <meshStandardMaterial color="#F59E0B" emissive="#F59E0B" emissiveIntensity={4.0} />
        </mesh>

        {/* 3 antennas (~10cm each) */}
        {[-0.08, 0, 0.08].map((xOff, i) => (
          <group key={`ant-${i}`}>
            <mesh position={[xOff, 0.10, -0.04]}>
              <cylinderGeometry args={[0.004, 0.004, 0.10, 6]} />
              <meshStandardMaterial color="#475569" metalness={0.6} />
            </mesh>
            {/* Antenna tip */}
            <mesh position={[xOff, 0.155, -0.04]}>
              <sphereGeometry args={[0.008, 8, 8]} />
              <meshStandardMaterial color="#94A3B8" metalness={0.8} />
            </mesh>
          </group>
        ))}

        {/* Animated TX beacon pulse rings */}
        <group ref={routerPulseRef} position={[0, 0.10, 0]}>
          {[0, 1, 2].map((idx) => (
            <mesh key={idx} rotation={[-Math.PI / 2, 0, 0]}>
              <ringGeometry args={[0.10, 0.12, 24]} />
              <meshBasicMaterial color="#F59E0B" transparent opacity={0.4} side={THREE.DoubleSide} />
            </mesh>
          ))}
        </group>

        {/* Amber point light */}
        <pointLight position={[0, 0.08, 0]} intensity={1.0} color="#F59E0B" distance={2.5} />

        {/* Label */}
        <Html position={[0, 0.38, 0]} center zIndexRange={[10, 0]}>
          <div style={{ pointerEvents: 'none' }} className="px-2.5 py-1 rounded-md bg-amber-950/92 border border-amber-500/85 text-amber-300 font-mono font-black text-[10px] whitespace-nowrap shadow-lg shadow-amber-500/15 flex items-center gap-1.5 backdrop-blur-sm">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse"></span>
            <span>Wi-Fi Router (TX Beacon)</span>
          </div>
        </Html>
      </group>

      {/* ══════════════════════════════════════════════════════════
          ESP32-S3 RECEIVERS — ~6cm PCB on 1m tripod stands
         ══════════════════════════════════════════════════════════ */}
      {nodes.map((node, nodeIdx) => {
        if (node.role === 'transmitter') return null;
        const pos = mapTo3D(node.x, node.y, node.z);

        return (
          <group key={node.id} position={pos}>
            {/* Tripod base plate */}
            <mesh position={[0, 0.005, 0]} rotation={[-Math.PI / 2, 0, 0]}>
              <circleGeometry args={[0.06, 12]} />
              <meshStandardMaterial color="#1E293B" metalness={0.5} />
            </mesh>

            {/* Tripod pole (1.0m) */}
            <mesh position={[0, 0.50, 0]}>
              <cylinderGeometry args={[0.012, 0.018, 1.0, 8]} />
              <meshStandardMaterial color="#334155" metalness={0.7} />
            </mesh>

            {/* Mounting plate */}
            <mesh position={[0, 1.01, 0]}>
              <boxGeometry args={[0.08, 0.008, 0.06]} />
              <meshStandardMaterial color="#334155" metalness={0.6} />
            </mesh>

            {/* ESP32 PCB (6cm x 3cm x 1.5cm) */}
            <mesh position={[0, 1.03, 0]}>
              <boxGeometry args={[0.06, 0.015, 0.03]} />
              <meshStandardMaterial color="#065F46" roughness={0.5} metalness={0.4} />
            </mesh>

            {/* Status LED (glowing cyan sphere) */}
            <mesh
              ref={(el) => { rxGlowRefs.current[nodeIdx] = el; }}
              position={[0, 1.055, 0]}
            >
              <sphereGeometry args={[0.018, 10, 10]} />
              <meshStandardMaterial color="#00F0FF" emissive="#00F0FF" emissiveIntensity={3.0} />
            </mesh>

            {/* Small antenna wire */}
            <mesh position={[0.02, 1.09, 0]}>
              <cylinderGeometry args={[0.003, 0.003, 0.06, 4]} />
              <meshStandardMaterial color="#94A3B8" metalness={0.6} />
            </mesh>

            {/* Ground reception ring */}
            <mesh position={[0, 0.012, 0]} rotation={[-Math.PI / 2, 0, 0]}>
              <ringGeometry args={[0.12, 0.15, 24]} />
              <meshBasicMaterial color="#00F0FF" transparent opacity={0.30} side={THREE.DoubleSide} />
            </mesh>

            {/* Cyan glow light */}
            <pointLight position={[0, 1.05, 0]} intensity={0.8} color="#00F0FF" distance={2.0} />

            {/* Label */}
            <Html position={[0, 1.32, 0]} center zIndexRange={[10, 0]}>
              <div style={{ pointerEvents: 'none' }} className="px-2.5 py-1 rounded-md bg-cyan-950/92 border border-cyan-500/85 text-cyan-300 font-mono font-black text-[10px] whitespace-nowrap shadow-lg shadow-cyan-500/15 flex items-center gap-1.5 backdrop-blur-sm">
                <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse"></span>
                <span>{node.name}</span>
              </div>
            </Html>
          </group>
        );
      })}
    </group>
  );
};
