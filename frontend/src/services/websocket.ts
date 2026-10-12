import type { SpatialTelemetryFrame } from '../types/csi';

type TelemetryCallback = (data: SpatialTelemetryFrame) => void;
type ConnectionCallback = (connected: boolean) => void;

class SpatialWebSocketClient {
  private url: string = 'ws://localhost:8000/api/v1/ws/csi';
  private socket: WebSocket | null = null;
  private listeners: Set<TelemetryCallback> = new Set();
  private connectionListeners: Set<ConnectionCallback> = new Set();
  private isConnected: boolean = false;
  private reconnectInterval: number = 2000;
  private shouldReconnect: boolean = true;

  public connect() {
    this.shouldReconnect = true;
    this.createSocket();
  }

  private createSocket() {
    try {
      this.socket = new WebSocket(this.url);

      this.socket.onopen = () => {
        this.isConnected = true;
        this.notifyConnectionState(true);
      };

      this.socket.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          if (payload.type === 'csi_spatial_telemetry_frame') {
            this.listeners.forEach((cb) => cb(payload as SpatialTelemetryFrame));
          }
        } catch (err) {
          console.error('Failed to parse WS spatial payload:', err);
        }
      };

      this.socket.onclose = () => {
        this.isConnected = false;
        this.notifyConnectionState(false);
        if (this.shouldReconnect) {
          setTimeout(() => this.createSocket(), this.reconnectInterval);
        }
      };

      this.socket.onerror = (err) => {
        console.warn('Spatial WebSocket connection error:', err);
        this.socket?.close();
      };
    } catch (e) {
      console.error('Failed to create WebSocket:', e);
      if (this.shouldReconnect) {
        setTimeout(() => this.createSocket(), this.reconnectInterval);
      }
    }
  }

  public disconnect() {
    this.shouldReconnect = false;
    if (this.socket) {
      this.socket.close();
    }
  }

  public subscribe(cb: TelemetryCallback): () => void {
    this.listeners.add(cb);
    return () => this.listeners.delete(cb);
  }

  public subscribeConnection(cb: ConnectionCallback): () => void {
    this.connectionListeners.add(cb);
    cb(this.isConnected);
    return () => this.connectionListeners.delete(cb);
  }

  private notifyConnectionState(state: boolean) {
    this.connectionListeners.forEach((cb) => cb(state));
  }

  public getStatus(): boolean {
    return this.isConnected;
  }
}

export const spatialWSClient = new SpatialWebSocketClient();
