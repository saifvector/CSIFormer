// ══════════════════════════════════════════════════════════════════════════════
// CSIFORMER WALKABLE NAVIGATION MESH ENGINE (NavMesh)
// Dynamic Walkable Surface Generator, Obstacle Cutouts & Pathfinding
// ══════════════════════════════════════════════════════════════════════════════

import { collisionManager } from './CollisionManager';

export type NavCellType = 'WALKABLE' | 'BLOCKED' | 'WARNING_BUFFER' | 'RESTRICTED';

export interface NavMeshCell {
  gridX: number;
  gridZ: number;
  worldX: number; // Three.js X [-5..5]
  worldZ: number; // Three.js Z [-4..4]
  type: NavCellType;
  distanceToObstacle: number;
}

export class NavMeshEngine {
  public readonly roomMinX = -4.8;
  public readonly roomMaxX = 4.8;
  public readonly roomMinZ = -3.8;
  public readonly roomMaxZ = 3.8;
  public readonly cellSize = 0.20; // 20cm spatial resolution

  public gridWidth = 0;
  public gridDepth = 0;
  private cells: NavMeshCell[][] = [];

  constructor() {
    this.rebuildNavMesh();
  }

  /**
   * Rebuilds the dynamic 2D navigation grid across the 10m x 8m room.
   */
  public rebuildNavMesh(): void {
    this.gridWidth = Math.ceil((this.roomMaxX - this.roomMinX) / this.cellSize);
    this.gridDepth = Math.ceil((this.roomMaxZ - this.roomMinZ) / this.cellSize);
    this.cells = [];

    for (let gx = 0; gx < this.gridWidth; gx++) {
      this.cells[gx] = [];
      const wx = this.roomMinX + gx * this.cellSize + this.cellSize / 2;

      for (let gz = 0; gz < this.gridDepth; gz++) {
        const wz = this.roomMinZ + gz * this.cellSize + this.cellSize / 2;
        const testRes = collisionManager.testPointCollision(wx, wz, 0.20);

        let type: NavCellType = 'WALKABLE';
        if (testRes.isColliding) {
          type = testRes.nearestCollider?.isRestricted ? 'RESTRICTED' : 'BLOCKED';
        } else if (testRes.closestDistance < 0.35) {
          type = 'WARNING_BUFFER';
        }

        this.cells[gx][gz] = {
          gridX: gx,
          gridZ: gz,
          worldX: wx,
          worldZ: wz,
          type,
          distanceToObstacle: testRes.closestDistance,
        };
      }
    }
  }

  public getCells(): NavMeshCell[][] {
    return this.cells;
  }

  /**
   * Returns walkable percentage of the lab floor.
   */
  public getWalkableStats(): { walkablePct: number; totalCells: number; walkableCells: number } {
    let total = 0;
    let walkable = 0;

    for (let gx = 0; gx < this.gridWidth; gx++) {
      for (let gz = 0; gz < this.gridDepth; gz++) {
        total++;
        if (this.cells[gx][gz].type === 'WALKABLE' || this.cells[gx][gz].type === 'WARNING_BUFFER') {
          walkable++;
        }
      }
    }

    return {
      totalCells: total,
      walkableCells: walkable,
      walkablePct: total > 0 ? (walkable / total) * 100 : 0,
    };
  }

  /**
   * Gets the nearest valid walkable cell from a world point (wx, wz).
   */
  public findNearestWalkable(wx: number, wz: number): [number, number] {
    const colRes = collisionManager.testPointCollision(wx, wz);
    if (!colRes.isColliding) {
      return [wx, wz];
    }
    return colRes.correctedPosition;
  }
}

export const navMeshEngine = new NavMeshEngine();
