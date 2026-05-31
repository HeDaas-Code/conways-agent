/**
 * WebSocket Session Client for Obsidian Plugin
 * 
 * Handles connection management, heartbeat, streaming messages, and auto-reconnect.
 */

import { WSMessage, parse } from './ws-messages';

export type ConnectionState = 'disconnected' | 'connecting' | 'connected' | 'reconnecting';

export interface WSSessionConfig {
  url: string;
  heartbeatInterval?: number;   // ms, default 30000 (30s)
  heartbeatTimeout?: number;    // ms, default 60000 (60s server-side)
  maxReconnectAttempts?: number;
  reconnectBaseDelay?: number;  // ms, default 1000
  reconnectMaxDelay?: number;   // ms, default 30000
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
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
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

        this.ws.onopen = () => {
          this.setState('connected');
          this.reconnectAttempts = 0;
          this.startHeartbeat();
          this.send('activate', null);
          resolve();
        };

        this.ws.onmessage = (event) => {
          this.handleMessage(event.data);
        };

        this.ws.onclose = (event) => {
          this.stopHeartbeat();
          this.handleDisconnect(event.code, event.reason || '');
        };

        this.ws.onerror = (event) => {
          const error = new Error('WebSocket error');
          this.errorHandlers.forEach(h => h(error));
          if (this.state === 'connecting') {
            reject(error);
          }
        };

      } catch (error) {
        this.setState('disconnected');
        reject(error);
      }
    });
  }

  disconnect(): void {
    this.stopHeartbeat();
    this.stopReconnect();
    // Prevent auto-reconnect
    this.reconnectAttempts = this.config.maxReconnectAttempts;

    if (this.ws) {
      this.send('deactivate', null);
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
      type: type as WSMessage['type'],
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
  } {
    return {
      state: this.state,
      reconnectAttempts: this.reconnectAttempts,
      lastPongAge: Date.now() - this.lastPong,
    };
  }

  // ─── Private Methods ──────────────────────────────────────────────────────

  private handleMessage(data: unknown): void {
    try {
      const parsed = parse(data);
      
      // Handle heartbeat responses
      if (parsed.type === 'heartbeat_ack' || parsed.type === 'pong') {
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
        // handleDisconnect will schedule next attempt if needed
      });
    }, delay);
  }

  private calculateBackoff(): number {
    const exponentialDelay = this.config.reconnectBaseDelay * Math.pow(2, this.reconnectAttempts);
    const jitter = Math.random() * 1000;
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

      // Send a heartbeat message
      this.send('heartbeat', { ts: Date.now() });
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
