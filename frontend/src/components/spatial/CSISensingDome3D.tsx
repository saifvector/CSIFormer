import React, { useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';

export const CSISensingDome3D: React.FC = () => {
  const meshRef = useRef<THREE.Mesh>(null);
  const wireframeRef = useRef<THREE.LineSegments>(null);

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime();
    if (meshRef.current) {
      const mat = meshRef.current.material as THREE.MeshBasicMaterial;
      mat.opacity = 0.04 + Math.sin(t * 1.5) * 0.02;
    }
    if (wireframeRef.current) {
      wireframeRef.current.rotation.y = t * 0.05;
    }
  });

  return (
    <group position={[0, 0, 0]}>
      {/* 1. Massive Triangulated Holographic Hemisphere Dome */}
      <mesh ref={meshRef} position={[0, 0.01, 0]}>
        <sphereGeometry args={[6.5, 32, 16, 0, Math.PI * 2, 0, Math.PI * 0.5]} />
        <meshBasicMaterial
          color="#00F0FF"
          transparent
          opacity={0.05}
          side={THREE.DoubleSide}
        />
      </mesh>

      {/* 2. Rotating Wireframe Mesh Energy Flow Lines */}
      <lineSegments ref={wireframeRef} position={[0, 0.01, 0]}>
        <wireframeGeometry args={[new THREE.SphereGeometry(6.52, 24, 12, 0, Math.PI * 2, 0, Math.PI * 0.5)]} />
        <lineBasicMaterial color="#00BFFF" opacity={0.12} transparent />
      </lineSegments>

      {/* 3. Base Perimeter Energy Ring */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.02, 0]}>
        <ringGeometry args={[6.48, 6.55, 64]} />
        <meshBasicMaterial color="#00F0FF" transparent opacity={0.4} side={THREE.DoubleSide} />
      </mesh>
    </group>
  );
};
