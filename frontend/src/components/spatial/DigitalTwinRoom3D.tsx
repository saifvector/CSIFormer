import React from 'react';
import * as THREE from 'three';

interface DigitalTwinRoom3DProps {
  showGrid?: boolean;
}

// ═══════════════════════════════════════════════════════════════
// DIGITAL TWIN ROOM — 10m x 8m x 3m realistic lab environment
// All furniture at correct real-world scale
// ═══════════════════════════════════════════════════════════════

export const DigitalTwinRoom3D: React.FC<DigitalTwinRoom3DProps> = ({ showGrid = true }) => {
  return (
    <group>
      {/* ── ROOM WIREFRAME: 10m x 3m x 8m ── */}
      <lineSegments position={[0, 1.5, 0]}>
        <edgesGeometry args={[new THREE.BoxGeometry(10.0, 3.0, 8.0)]} />
        <lineBasicMaterial color="#00F0FF" opacity={0.18} transparent />
      </lineSegments>

      {/* ── FLOOR GRID ── */}
      {showGrid && (
        <gridHelper args={[10.0, 20, '#00BFFF', '#081120']} position={[0, 0.002, 0]} />
      )}

      {/* ── SEMANTIC FLOOR ZONES (very subtle tints) ── */}
      <mesh position={[-3.4, 0.004, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[3.2, 8.0]} />
        <meshBasicMaterial color="#00F0FF" transparent opacity={0.025} side={THREE.DoubleSide} />
      </mesh>
      <mesh position={[3.4, 0.004, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[3.2, 8.0]} />
        <meshBasicMaterial color="#00BFFF" transparent opacity={0.025} side={THREE.DoubleSide} />
      </mesh>
      <mesh position={[0, 0.004, 2.0]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[3.6, 4.0]} />
        <meshBasicMaterial color="#00F0FF" transparent opacity={0.03} side={THREE.DoubleSide} />
      </mesh>

      {/* ── RESTRICTED ZONE ── */}
      <group position={[-3.5, 0.006, -2.0]}>
        <mesh rotation={[-Math.PI / 2, 0, 0]}>
          <planeGeometry args={[2.0, 2.0]} />
          <meshBasicMaterial color="#EF4444" transparent opacity={0.08} side={THREE.DoubleSide} />
        </mesh>
        <lineSegments rotation={[-Math.PI / 2, 0, 0]}>
          <edgesGeometry args={[new THREE.PlaneGeometry(2.0, 2.0)]} />
          <lineBasicMaterial color="#EF4444" opacity={0.5} />
        </lineSegments>
      </group>

      {/* ═══════════════════════════════════════════
          FURNITURE — realistic scale, visually secondary
         ═══════════════════════════════════════════ */}

      {/* Workstation Desk: 1.4m x 0.75m surface at 0.75m height */}
      <group position={[-1.8, 0, 1.5]}>
        <mesh position={[0, 0.75, 0]}>
          <boxGeometry args={[1.4, 0.03, 0.70]} />
          <meshStandardMaterial color="#1E293B" roughness={0.4} metalness={0.6} />
        </mesh>
        {[[-0.65, 0.375, -0.30], [0.65, 0.375, -0.30], [-0.65, 0.375, 0.30], [0.65, 0.375, 0.30]].map((p, i) => (
          <mesh key={`dl${i}`} position={p as [number, number, number]}>
            <cylinderGeometry args={[0.018, 0.018, 0.75, 6]} />
            <meshStandardMaterial color="#0F172A" metalness={0.7} />
          </mesh>
        ))}
        {/* Monitor: 45cm x 28cm */}
        <mesh position={[0, 0.93, -0.22]}>
          <boxGeometry args={[0.45, 0.28, 0.02]} />
          <meshStandardMaterial color="#020617" roughness={0.1} metalness={0.9} />
        </mesh>
        <mesh position={[0, 0.82, -0.20]}>
          <cylinderGeometry args={[0.022, 0.035, 0.06, 8]} />
          <meshStandardMaterial color="#0F172A" metalness={0.8} />
        </mesh>
      </group>

      {/* Office Chair */}
      <group position={[-1.8, 0, 2.3]}>
        <mesh position={[0, 0.44, 0]}>
          <boxGeometry args={[0.42, 0.04, 0.42]} />
          <meshStandardMaterial color="#1E293B" roughness={0.6} />
        </mesh>
        <mesh position={[0, 0.68, 0.18]}>
          <boxGeometry args={[0.40, 0.44, 0.03]} />
          <meshStandardMaterial color="#1E293B" roughness={0.6} />
        </mesh>
        <mesh position={[0, 0.22, 0]}>
          <cylinderGeometry args={[0.018, 0.018, 0.44, 6]} />
          <meshStandardMaterial color="#0F172A" metalness={0.7} />
        </mesh>
      </group>

      {/* Round Meeting Table: 0.8m radius, 0.72m tall */}
      <group position={[0, 0, 2.0]}>
        <mesh position={[0, 0.72, 0]}>
          <cylinderGeometry args={[0.80, 0.80, 0.03, 24]} />
          <meshStandardMaterial color="#1E293B" roughness={0.4} metalness={0.5} />
        </mesh>
        <mesh position={[0, 0.36, 0]}>
          <cylinderGeometry args={[0.12, 0.22, 0.72, 12]} />
          <meshStandardMaterial color="#0F172A" metalness={0.6} />
        </mesh>
      </group>

      {/* Small bookshelf along back wall */}
      <group position={[3.5, 0, -3.6]}>
        <mesh position={[0, 0.5, 0]}>
          <boxGeometry args={[1.2, 1.0, 0.35]} />
          <meshStandardMaterial color="#1E293B" roughness={0.5} metalness={0.4} />
        </mesh>
        {/* Shelf dividers */}
        <mesh position={[0, 0.30, 0]}>
          <boxGeometry args={[1.15, 0.015, 0.32]} />
          <meshStandardMaterial color="#0F172A" />
        </mesh>
        <mesh position={[0, 0.65, 0]}>
          <boxGeometry args={[1.15, 0.015, 0.32]} />
          <meshStandardMaterial color="#0F172A" />
        </mesh>
      </group>
    </group>
  );
};
