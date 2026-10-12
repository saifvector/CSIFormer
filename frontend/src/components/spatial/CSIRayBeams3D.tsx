import React, { useRef, useMemo } from 'react';
import { useFrame } from '@react-three/fiber';
import { Line } from '@react-three/drei';
import * as THREE from 'three';

interface CSIRayBeams3DProps {
  nodes?: Array<{
    id: string;
    x: number;
    y: number;
    z: number;
    role: string;
  }>;
  target?: {
    x: number;
    y: number;
    z: number;
  };
}

// ═══════════════════════════════════════════════════════════════
// RF SIGNAL VISUALIZATION
// Router TX → Human Reflection → ESP32 RX
// Thin beams + subtle packet flow particles
// ═══════════════════════════════════════════════════════════════

export const CSIRayBeams3D: React.FC<CSIRayBeams3DProps> = ({ nodes, target }) => {
  const packetRef = useRef<THREE.Group>(null);

  // Router position matches SensorNodes3D
  const routerTx: [number, number, number] = [-2.3, 0.82, 1.2];

  const rxNodes = (nodes && nodes.filter((n) => n.role === 'receiver')) || [
    { id: 'rx-1', x: 0.5, y: 0.5, z: 1.0, role: 'receiver' },
    { id: 'rx-2', x: 9.5, y: 0.5, z: 1.0, role: 'receiver' },
    { id: 'rx-3', x: 5.0, y: 7.5, z: 1.0, role: 'receiver' },
  ];

  const targetPos = target || { x: 5.0, y: 4.0, z: 1.0 };
  // Human torso height
  const humanTorso: [number, number, number] = [
    (targetPos.x ?? 5.0) - 5.0,
    0.95,
    (targetPos.y ?? 4.0) - 4.0
  ];

  // Build packet endpoints
  const packetPairs = useMemo(() => {
    const pairs: { from: THREE.Vector3; to: THREE.Vector3 }[] = [];
    // Router → Human
    pairs.push({
      from: new THREE.Vector3(...routerTx),
      to: new THREE.Vector3(...humanTorso),
    });
    rxNodes.forEach((rx) => {
      // Tripod-top antenna height = 1.05m
      pairs.push({
        from: new THREE.Vector3(...humanTorso),
        to: new THREE.Vector3(rx.x - 5.0, 1.05, rx.y - 4.0),
      });
    });
    return pairs;
  }, [rxNodes, humanTorso]);

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime();
    if (packetRef.current) {
      packetRef.current.children.forEach((child, idx) => {
        const progress = ((t * 0.7 + idx * 0.25) % 1.0);
        if (child.userData.from && child.userData.to) {
          child.position.lerpVectors(
            child.userData.from as THREE.Vector3,
            child.userData.to as THREE.Vector3,
            progress
          );
        }
      });
    }
  });

  return (
    <group>
      {/* TX beam: Router → Human torso (thin amber) */}
      <Line
        points={[routerTx, humanTorso]}
        color="#F59E0B"
        lineWidth={1.5}
        transparent
        opacity={0.55}
      />

      {/* CSI reflection beams: Human torso → each ESP32 RX (thin cyan) */}
      {rxNodes.map((rx) => {
        const rxTuple: [number, number, number] = [rx.x - 5.0, 1.05, rx.y - 4.0];
        return (
          <group key={rx.id}>
            <Line
              points={[humanTorso, rxTuple]}
              color="#00F0FF"
              lineWidth={1.5}
              transparent
              opacity={0.55}
            />
            {/* Faint direct LoS (dashed) */}
            <Line
              points={[routerTx, rxTuple]}
              color="#00BFFF"
              lineWidth={0.7}
              transparent
              opacity={0.12}
              dashed
              dashScale={12}
            />
          </group>
        );
      })}

      {/* Animated packet flow particles */}
      <group ref={packetRef}>
        {packetPairs.map((pp, idx) => (
          <mesh key={`pkt-${idx}`} userData={{ from: pp.from, to: pp.to }}>
            <sphereGeometry args={[0.025, 6, 6]} />
            <meshBasicMaterial color="#7DF9FF" transparent opacity={0.85} />
          </mesh>
        ))}
      </group>
    </group>
  );
};
