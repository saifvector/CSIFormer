// ══════════════════════════════════════════════════════════════════════════════
// CSIFORMER SPATIAL COLLISION MANAGER
// Real-Time 3D Physics Colliders, Distance Fields & Penetration Resolvers
// ══════════════════════════════════════════════════════════════════════════════

export type ColliderType = 'BOX' | 'CYLINDER' | 'SPHERE' | 'ROOM_BOUNDS';

export interface BaseCollider {
  id: string;
  name: string;
  type: ColliderType;
  enabled: boolean;
  isRestricted?: boolean;
}

export interface BoxCollider extends BaseCollider {
  type: 'BOX';
  center: [number, number, number]; // [x, y, z] in Three.js coordinates [-5..5, 0..3, -4..4]
  size: [number, number, number];   // [width, height, depth]
}

export interface CylinderCollider extends BaseCollider {
  type: 'CYLINDER';
  center: [number, number, number];
  radius: number;
  height: number;
}

export interface SphereCollider extends BaseCollider {
  type: 'SPHERE';
  center: [number, number, number];
  radius: number;
}

export interface RoomBoundsCollider extends BaseCollider {
  type: 'ROOM_BOUNDS';
  minX: number;
  maxX: number;
  minZ: number;
  maxZ: number;
}

export type Collider = BoxCollider | CylinderCollider | SphereCollider | RoomBoundsCollider;

export interface CollisionResult {
  isColliding: boolean;
  penetrationDepth: number;
  closestDistance: number;
  nearestCollider: Collider | null;
  surfaceNormal: [number, number]; // 2D normal [nx, nz]
  correctedPosition: [number, number]; // [x, z] in Three.js coordinates
}

export class SpatialCollisionManager {
  private colliders: Collider[] = [];
  public readonly avatarRadius: number = 0.30; // 30cm avatar body buffer

  constructor() {
    this.initializeDefaultRoomColliders();
  }

  /**
   * Initializes all physical lab obstacles with realistic bounds matching DigitalTwinRoom3D
   */
  public initializeDefaultRoomColliders(): void {
    this.colliders = [
      // 1. Room Outer Boundary (10m x 8m room, wall clearance 0.35m from perimeter)
      {
        id: 'room_boundary',
        name: 'Room Perimeter Walls',
        type: 'ROOM_BOUNDS',
        enabled: true,
        minX: -4.65,
        maxX: 4.65,
        minZ: -3.65,
        maxZ: 3.65,
      },

      // 2. Workstation Desk (1.4m x 0.70m at [-1.8, 0, 1.5], buffer size 1.6m x 0.9m)
      {
        id: 'workstation_desk',
        name: 'Workstation Desk',
        type: 'BOX',
        enabled: true,
        center: [-1.8, 0.45, 1.5],
        size: [1.60, 0.90, 0.90],
      },

      // 3. Office Chair (0.42m x 0.42m at [-1.8, 0, 2.3])
      {
        id: 'office_chair',
        name: 'Office Chair',
        type: 'BOX',
        enabled: true,
        center: [-1.8, 0.40, 2.3],
        size: [0.65, 0.80, 0.65],
      },

      // 4. Round Meeting Table (0.80m radius at [0, 0, 2.0])
      {
        id: 'round_meeting_table',
        name: 'Round Meeting Table',
        type: 'CYLINDER',
        enabled: true,
        center: [0.0, 0.36, 2.0],
        radius: 0.95, // 0.80m table + 0.15m buffer
        height: 0.75,
      },

      // 5. Bookshelf along back wall (1.2m x 0.35m at [3.5, 0, -3.6])
      {
        id: 'bookshelf_wall',
        name: 'Storage Bookshelf',
        type: 'BOX',
        enabled: true,
        center: [3.5, 0.50, -3.6],
        size: [1.45, 1.00, 0.55],
      },

      // 6. Router Pedestal / Desk Area at [-2.3, 0.76, 1.2]
      {
        id: 'router_beacon_zone',
        name: 'Wi-Fi Router (TX Beacon)',
        type: 'CYLINDER',
        enabled: true,
        center: [-2.3, 0.40, 1.2],
        radius: 0.50,
        height: 0.80,
      },

      // 7. ESP32-S3 RX West Node Tripod at [-4.9, 0, 0.0]
      {
        id: 'esp32_rx_west',
        name: 'ESP32 RX West Tripod',
        type: 'SPHERE',
        enabled: true,
        center: [-4.9, 0.50, 0.0],
        radius: 0.45,
      },

      // 8. ESP32-S3 RX East Node Tripod at [4.9, 0, 1.5]
      {
        id: 'esp32_rx_east',
        name: 'ESP32 RX East Tripod',
        type: 'SPHERE',
        enabled: true,
        center: [4.9, 0.50, 1.5],
        radius: 0.45,
      },

      // 9. ESP32-S3 RX South Node Tripod at [0.0, 0, -3.9]
      {
        id: 'esp32_rx_south',
        name: 'ESP32 RX South Tripod',
        type: 'SPHERE',
        enabled: true,
        center: [0.0, 0.50, -3.9],
        radius: 0.45,
      },

      // 10. Restricted High-Voltage Sensing Zone at [-3.5, 0, -2.0]
      {
        id: 'restricted_zone',
        name: 'Restricted Hazardous Zone',
        type: 'BOX',
        enabled: true,
        isRestricted: true,
        center: [-3.5, 0.10, -2.0],
        size: [2.20, 0.30, 2.20],
      },
    ];
  }

  public getColliders(): Collider[] {
    return this.colliders;
  }

  public addCollider(collider: Collider): void {
    this.colliders.push(collider);
  }

  /**
   * Tests a 2D floor position (px, pz) against all colliders and returns the nearest collision state and projected position.
   * @param px Three.js X coordinate [-5..5]
   * @param pz Three.js Z coordinate [-4..4]
   * @param customRadius Optional custom human radius
   */
  public testPointCollision(px: number, pz: number, customRadius?: number): CollisionResult {
    const r = customRadius ?? this.avatarRadius;
    let isColliding = false;
    let minDistance = Infinity;
    let maxPenetration = 0;
    let nearestCollider: Collider | null = null;
    let normal: [number, number] = [0, 0];
    let correctedX = px;
    let correctedZ = pz;

    for (const col of this.colliders) {
      if (!col.enabled) continue;

      if (col.type === 'ROOM_BOUNDS') {
        // Enforce room walls clamp
        let clampedX = correctedX;
        let clampedZ = correctedZ;
        let wallColliding = false;

        if (correctedX - r < col.minX) {
          const pen = col.minX - (correctedX - r);
          clampedX = col.minX + r;
          maxPenetration = Math.max(maxPenetration, pen);
          wallColliding = true;
          normal = [1, 0];
        } else if (correctedX + r > col.maxX) {
          const pen = (correctedX + r) - col.maxX;
          clampedX = col.maxX - r;
          maxPenetration = Math.max(maxPenetration, pen);
          wallColliding = true;
          normal = [-1, 0];
        }

        if (correctedZ - r < col.minZ) {
          const pen = col.minZ - (correctedZ - r);
          clampedZ = col.minZ + r;
          maxPenetration = Math.max(maxPenetration, pen);
          wallColliding = true;
          normal = [0, 1];
        } else if (correctedZ + r > col.maxZ) {
          const pen = (correctedZ + r) - col.maxZ;
          clampedZ = col.maxZ - r;
          maxPenetration = Math.max(maxPenetration, pen);
          wallColliding = true;
          normal = [0, -1];
        }

        if (wallColliding) {
          isColliding = true;
          nearestCollider = col;
          correctedX = clampedX;
          correctedZ = clampedZ;
        }
      } else if (col.type === 'BOX') {
        const halfW = col.size[0] / 2;
        const halfD = col.size[2] / 2;
        const cx = col.center[0];
        const cz = col.center[2];

        // Closest point on AABB to (correctedX, correctedZ)
        const closestX = Math.max(cx - halfW, Math.min(correctedX, cx + halfW));
        const closestZ = Math.max(cz - halfD, Math.min(correctedZ, cz + halfD));

        const dx = correctedX - closestX;
        const dz = correctedZ - closestZ;
        const distSq = dx * dx + dz * dz;
        const dist = Math.sqrt(distSq);

        // Check if inside or overlapping with avatar radius
        const isInside = Math.abs(correctedX - cx) <= halfW && Math.abs(correctedZ - cz) <= halfD;

        if (isInside || dist < r) {
          isColliding = true;
          const pen = isInside ? r + Math.min(halfW - Math.abs(correctedX - cx), halfD - Math.abs(correctedZ - cz)) : r - dist;
          if (pen > maxPenetration) {
            maxPenetration = pen;
            nearestCollider = col;

            if (isInside) {
              // Push out along shortest axis
              const pushX = (halfW + r) - Math.abs(correctedX - cx);
              const pushZ = (halfD + r) - Math.abs(correctedZ - cz);
              if (pushX < pushZ) {
                const sgn = correctedX >= cx ? 1 : -1;
                correctedX = cx + sgn * (halfW + r);
                normal = [sgn, 0];
              } else {
                const sgn = correctedZ >= cz ? 1 : -1;
                correctedZ = cz + sgn * (halfD + r);
                normal = [0, sgn];
              }
            } else if (dist > 0.001) {
              const nx = dx / dist;
              const nz = dz / dist;
              correctedX = closestX + nx * r;
              correctedZ = closestZ + nz * r;
              normal = [nx, nz];
            }
          }
        } else {
          const edgeDist = dist - r;
          if (edgeDist < minDistance) {
            minDistance = edgeDist;
          }
        }
      } else if (col.type === 'CYLINDER' || col.type === 'SPHERE') {
        const cx = col.center[0];
        const cz = col.center[2];
        const rad = col.radius;

        const dx = correctedX - cx;
        const dz = correctedZ - cz;
        const dist = Math.sqrt(dx * dx + dz * dz);
        const minDistReq = rad + r;

        if (dist < minDistReq) {
          isColliding = true;
          const pen = minDistReq - dist;
          if (pen > maxPenetration) {
            maxPenetration = pen;
            nearestCollider = col;

            if (dist > 0.001) {
              const nx = dx / dist;
              const nz = dz / dist;
              correctedX = cx + nx * minDistReq;
              correctedZ = cz + nz * minDistReq;
              normal = [nx, nz];
            } else {
              correctedX = cx + minDistReq;
              normal = [1, 0];
            }
          }
        } else {
          const edgeDist = dist - minDistReq;
          if (edgeDist < minDistance) {
            minDistance = edgeDist;
          }
        }
      }
    }

    return {
      isColliding,
      penetrationDepth: maxPenetration,
      closestDistance: isColliding ? 0 : minDistance,
      nearestCollider,
      surfaceNormal: normal,
      correctedPosition: [correctedX, correctedZ],
    };
  }

  /**
   * Helper to check whether a 2D floor position is completely clear and valid.
   */
  public isWalkable(px: number, pz: number): boolean {
    const res = this.testPointCollision(px, pz);
    return !res.isColliding;
  }
}

export const collisionManager = new SpatialCollisionManager();
