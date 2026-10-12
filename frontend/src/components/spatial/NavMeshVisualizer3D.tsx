import React, { useMemo } from 'react';
import * as THREE from 'three';
import { navMeshEngine } from '../../services/spatial/NavMeshEngine';
import { collisionManager } from '../../services/spatial/CollisionManager';

interface NavMeshVisualizer3DProps {
  visible?: boolean;
}

export const NavMeshVisualizer3D: React.FC<NavMeshVisualizer3DProps> = ({ visible = true }) => {
  const cells = useMemo(() => navMeshEngine.getCells(), []);
  const colliders = useMemo(() => collisionManager.getColliders(), []);

  if (!visible) return null;

  return (
    <group position={[0, 0.003, 0]}>
      {/* ── 1. WALKABLE CELL GRID TILES ── */}
      {cells.flatMap((row, rx) =>
        row.map((cell, cz) => {
          if (cell.type === 'BLOCKED' || cell.type === 'RESTRICTED') return null;

          const isWarning = cell.type === 'WARNING_BUFFER';
          const color = isWarning ? '#F59E0B' : '#00F0FF';
          const opacity = isWarning ? 0.04 : 0.025;

          return (
            <mesh
              key={`cell_${rx}_${cz}`}
              position={[cell.worldX, 0, cell.worldZ]}
              rotation={[-Math.PI / 2, 0, 0]}
            >
              <planeGeometry args={[navMeshEngine.cellSize * 0.92, navMeshEngine.cellSize * 0.92]} />
              <meshBasicMaterial color={color} transparent opacity={opacity} side={THREE.DoubleSide} />
            </mesh>
          );
        })
      )}

      {/* ── 2. OBSTACLE COLLIDER FOOTPRINT HIGHLIGHTS ── */}
      {colliders.map((col) => {
        if (!col.enabled || col.type === 'ROOM_BOUNDS') return null;

        const isRestricted = col.isRestricted;
        const color = isRestricted ? '#EF4444' : '#F59E0B';

        if (col.type === 'BOX') {
          return (
            <group key={`col_vis_${col.id}`} position={[col.center[0], 0.005, col.center[2]]}>
              <lineSegments rotation={[-Math.PI / 2, 0, 0]}>
                <edgesGeometry args={[new THREE.PlaneGeometry(col.size[0], col.size[2])]} />
                <lineBasicMaterial color={color} opacity={0.65} transparent linewidth={1.5} />
              </lineSegments>
            </group>
          );
        } else if (col.type === 'CYLINDER' || col.type === 'SPHERE') {
          return (
            <group key={`col_vis_${col.id}`} position={[col.center[0], 0.005, col.center[2]]}>
              <mesh rotation={[-Math.PI / 2, 0, 0]}>
                <ringGeometry args={[col.radius - 0.04, col.radius, 32]} />
                <meshBasicMaterial color={color} transparent opacity={0.55} side={THREE.DoubleSide} />
              </mesh>
            </group>
          );
        }
        return null;
      })}
    </group>
  );
};
