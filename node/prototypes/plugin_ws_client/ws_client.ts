/**
 * WebSocket Session Client for Obsidian Plugin
 * 
 * PROTOYPE - answers: How to handle connection management, heartbeat, 
 * streaming messages, and auto-reconnect in a browser environment?
 */

import { WebSocket } from 'ws';

export type ConnectionState = 'disconnected' | 'connecting' | 'connected' | 'reconnecting';

export interface WSMessage {
  type: string;
  payload: unknown;
  id?: string;
  timestamp?: number;
}

export interface WSSessionConfig {
  url: string;
  heartbeatInterval?: number;  // ms, default 30000 (30s)
  heartbeatTimeout?: number;   // ms, default 60000 (60s server-side)
  maxReconnectAttempts?: number;
  reconnectBaseDelay?: number; // ms, default 1000
  reconnectMaxDelay?: number;  // ms, default 30000
}

type MessageHandler = (msg: WSMessage) => void;
type StateChangeHandler = (state: ConnectionState) => void;
type ErrorHandler = (error: Error) => void;

const DEFAULT_CONFIG: Required<WSSessionConfig> = {
  url: 'ws://localhost:8000/ws',
  heartbeatInterval: 30000,    // Client sends ping every 30s
  heartbeatTimeout: 60000,      // Server timeout is 60s
  maxReconnectAttempts: 5,
  reconnectBaseDelay: 1000,
  reconnectMaxDelay: 30000,
};

export class WSSession {
  private ws: WebSocket | null = null;
  private config: Required<WSSessionConfig>;
  private state: ConnectionState = 'disconnected';
  private reconnectAttempts = 0;
  private heartbeatTimer: NodeJS.Timeout | null = null;
  private reconnectTimer: NodeJS.Timeout | null = null;
  private lastPong: number = 0;
  
  private messageHandlers: Set<MessageHandler> = new Set();
  private stateChangeHandlers: Set<StateChangeHandler> = new Set();
  private errorHandlers: Set<ErrorHandler> = new Set();

  constructor(config: Partial<WSSessionConfig> = {}) {
    this.config = { ...DEFAULT_CONFIG, ...config };
    this.lastPong = Date.now();
  }

  // ─── Public API ───────────────────────────────────────────────────────────

  async connect(): Promise<void> {
    if (this.state === 'connected' || this.state === 'connecting') {
      return;
    }

    this.setState('connecting');

    return new Promise((resolve, reject) => {
      try {
        this.ws = new WebSocket(this.config.url);

        this.ws.on('open', () => {
          this.setState('connected');
          this.reconnectAttempts = 0;
          this.startHeartbeat();
          resolve();
        });

        this.ws.on('message', (data) => {
          this.handleMessage(data);
        });

        this.ws.on('close', (code, reason) => {
          this.stopHeartbeat();
          this.handleDisconnect(code, reason?.toString() || '');
        });

        this.ws.on('error', (error) => {
          this.errorHandlers.forEach(h => h(error));
          if (this.state === 'connecting') {
            reject(error);
          }
        });

        this.ws.on('pong', () => {
          this.lastPong = Date.now();
        });

      } catch (error) {
        this.setState('disconnected');
        reject(error);
      }
    });
  }

  disconnect(): void {
    this.stopHeartbeat();
    this.stopReconnect();
    this.reconnectAttempts = this.config.maxReconnectAttempts; // Prevent auto-reconnect

    if (this.ws) {
      this.ws.close(1000, 'Client initiated disconnect');
      this.ws = null;
    }

    this.setState('disconnected');
  }

  send(type: string, payload: unknown): boolean {
    if (this.state !== 'connected' || !this.ws) {
      return false;
    }

    const message: WSMessage = {
      type,
      payload,
      id: this.generateId(),
      timestamp: Date.now(),
    };

    this.ws.send(JSON.stringify(message));
    return true;
  }

  // ─── Event Handlers ───────────────────────────────────────────────────────

  onMessage(handler: MessageHandler): () => void {
    this.messageHandlers.add(handler);
    return () => this.messageHandlers.delete(handler);
  }

  onStateChange(handler: StateChangeHandler): () => void {
    this.stateChangeHandlers.add(handler);
    return () => this.stateChangeHandlers.delete(handler);
  }

  onError(handler: ErrorHandler): () => void {
    this.errorHandlers.add(handler);
    return () => this.errorHandlers.delete(handler);
  }

  // ─── State Inspection ─────────────────────────────────────────────────────

  getState(): ConnectionState {
    return this.state;
  }

  getStateSnapshot(): {
    state: ConnectionState;
    reconnectAttempts: number;
    lastPongAge: number;
    pendingMessages: number;
  } {
    return {
      state: this.state,
      reconnectAttempts: this.reconnectAttempts,
      lastPongAge: Date.now() - this.lastPong,
      pendingMessages: 0, // Would track in production
    };
  }

  // ─── Private Methods ──────────────────────────────────────────────────────

  private handleMessage(data: unknown): void {
    try {
      let parsed: WSMessage;
      if (typeof data === 'string') {
        parsed = JSON.parse(data);
      } else if (Buffer.isBuffer(data)) {
        parsed = JSON.parse(data.toString());
      } else if (data instanceof Uint8Array) {
        parsed = JSON.parse(Buffer.from(data).toString());
      } else {
        parsed = JSON.parse(String(data));
      }
      
      // Handle heartbeat responses from server
      if (parsed.type === 'pong' || parsed.type === 'heartbeat') {
        this.lastPong = Date.now();
        return;
      }

      this.messageHandlers.forEach(handler => handler(parsed));
    } catch (error) {
      console.error('Failed to parse message:', error);
    }
  }

  private handleDisconnect(code: number, reason: string): void {
    this.ws = null;

    // Don't auto-reconnect if client initiated disconnect (code 1000)
    if (code === 1000 || this.reconnectAttempts >= this.config.maxReconnectAttempts) {
      this.setState('disconnected');
      return;
    }

    this.scheduleReconnect();
  }

  private scheduleReconnect(): void {
    if (this.state === 'reconnecting') return;

    this.setState('reconnecting');
    const delay = this.calculateBackoff();

    this.reconnectTimer = setTimeout(() => {
      this.reconnectAttempts++;
      this.connect().catch(() => {
        // handleReconnect will schedule next attempt if needed
      });
    }, delay);
  }

  private calculateBackoff(): number {
    const exponentialDelay = this.config.reconnectBaseDelay * Math.pow(2, this.reconnectAttempts);
    const jitter = Math.random() * 1000; // Add randomness to prevent thundering herd
    return Math.min(exponentialDelay + jitter, this.config.reconnectMaxDelay);
  }

  private startHeartbeat(): void {
    this.lastPong = Date.now();

    this.heartbeatTimer = setInterval(() => {
      if (this.state !== 'connected' || !this.ws) {
        return;
      }

      // Check if we've exceeded server timeout
      if (Date.now() - this.lastPong > this.config.heartbeatTimeout) {
        console.warn('Heartbeat timeout exceeded, reconnecting...');
        this.ws.close(4000, 'Heartbeat timeout');
        return;
      }

      // Send ping to server
      this.ws.ping();
      
      // Also send a heartbeat message for servers that don't support WS ping/pong
      this.send('ping', { ts: Date.now() });
    }, this.config.heartbeatInterval);
  }

  private stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  private stopReconnect(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  private setState(state: ConnectionState): void {
    if (this.state === state) return;
    this.state = state;
    this.stateChangeHandlers.forEach(handler => handler(state));
  }

  private generateId(): string {
    return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  }
}
