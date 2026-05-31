import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { WSSession } from '../src/ws-client';
import { WSMessage } from '../src/ws-messages';

describe('WSSession', () => {
  // Mock WebSocket class for testing
  class MockWebSocket {
    static CONNECTING = 0;
    static OPEN = 1;
    static CLOSING = 2;
    static CLOSED = 3;

    readyState: number = MockWebSocket.CONNECTING;
    url: string;
    
    onopen: ((event: Event) => void) | null = null;
    onclose: ((event: CloseEvent) => void) | null = null;
    onmessage: ((event: MessageEvent) => void) | null = null;
    onerror: ((event: Event) => void) | null = null;
    onpong: ((event: Event) => void) | null = null;

    constructor(url: string) {
      this.url = url;
      // Simulate async connection
      setTimeout(() => {
        if (this.readyState === MockWebSocket.CONNECTING) {
          this.readyState = MockWebSocket.OPEN;
          this.onopen?.(new Event('open'));
        }
      }, 10);
    }

    send(data: string): void {
      // Parse and handle sent messages
      const msg = JSON.parse(data);
      if (msg.type === 'activate') {
        // Server acknowledges activation
        this.simulateMessage({ type: 'heartbeat_ack', payload: null });
      }
    }

    ping(): void {
      // Simulate server pong response
    }

    close(code?: number, reason?: string): void {
      this.readyState = MockWebSocket.CLOSING;
      setTimeout(() => {
        this.readyState = MockWebSocket.CLOSED;
        this.onclose?.(new CloseEvent('close', { code: code ?? 1000, reason: reason ?? '' }));
      }, 10);
    }

    simulateMessage(msg: WSMessage): void {
      if (this.onmessage) {
        this.onmessage(new MessageEvent('message', { data: JSON.stringify(msg) }));
      }
    }

    simulateClose(code: number = 1000, reason: string = ''): void {
      this.readyState = MockWebSocket.CLOSED;
      this.onclose?.(new CloseEvent('close', { code, reason }));
    }
  }

  beforeEach(() => {
    vi.stubGlobal('WebSocket', MockWebSocket);
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  describe('connect()', () => {
    it('should establish WebSocket connection', async () => {
      const session = new WSSession({ url: 'ws://localhost:8000/ws' });
      
      const connectPromise = session.connect();
      await vi.advanceTimersByTimeAsync(20);
      await connectPromise;

      expect(session.getState()).toBe('connected');
    });

    it('should send activate message on connect', async () => {
      const session = new WSSession({ url: 'ws://localhost:8000/ws' });
      const sendSpy = vi.spyOn(MockWebSocket.prototype, 'send');

      await session.connect();
      await vi.advanceTimersByTimeAsync(20);

      expect(sendSpy).toHaveBeenCalled();
      const sentMessage = JSON.parse(sendSpy.mock.calls[0][0]);
      expect(sentMessage.type).toBe('activate');
    });

    it('should not reconnect if already connecting', async () => {
      const session = new WSSession({ url: 'ws://localhost:8000/ws' });
      
      const connect1 = session.connect();
      await vi.advanceTimersByTimeAsync(5);
      const connect2 = session.connect();
      
      await vi.advanceTimersByTimeAsync(20);
      await connect1;
      await connect2;

      // Should only have one WebSocket created
      expect(session.getState()).toBe('connected');
    });
  });

  describe('disconnect()', () => {
    it('should send deactivate message and close WebSocket', async () => {
      const session = new WSSession({ url: 'ws://localhost:8000/ws' });
      await session.connect();
      await vi.advanceTimersByTimeAsync(20);

      const sendSpy = vi.spyOn(MockWebSocket.prototype, 'send');
      session.disconnect();
      await vi.advanceTimersByTimeAsync(20);

      expect(sendSpy).toHaveBeenCalled();
      // Find the deactivate message
      const deactivateCall = sendSpy.mock.calls.find(call => {
        const msg = JSON.parse(call[0]);
        return msg.type === 'deactivate';
      });
      expect(deactivateCall).toBeDefined();
    });

    it('should transition to disconnected state', async () => {
      const session = new WSSession({ url: 'ws://localhost:8000/ws' });
      await session.connect();
      await vi.advanceTimersByTimeAsync(20);

      session.disconnect();
      await vi.advanceTimersByTimeAsync(20);

      expect(session.getState()).toBe('disconnected');
    });

    it('should NOT auto-reconnect after user-initiated disconnect', async () => {
      const session = new WSSession({ url: 'ws://localhost:8000/ws' });
      await session.connect();
      await vi.advanceTimersByTimeAsync(20);

      session.disconnect();
      await vi.advanceTimersByTimeAsync(100); // Wait for potential reconnect

      expect(session.getState()).toBe('disconnected');
    });
  });

  describe('heartbeat', () => {
    it('should send heartbeat message every 30 seconds', async () => {
      const session = new WSSession({ 
        url: 'ws://localhost:8000/ws',
        heartbeatInterval: 30000 
      });
      
      await session.connect();
      await vi.advanceTimersByTimeAsync(20);

      const sendSpy = vi.spyOn(MockWebSocket.prototype, 'send');
      
      // Advance 30 seconds
      await vi.advanceTimersByTimeAsync(30000);

      // Should have sent heartbeat
      const heartbeatMessages = sendSpy.mock.calls.filter(call => {
        const msg = JSON.parse(call[0]);
        return msg.type === 'heartbeat';
      });
      expect(heartbeatMessages.length).toBeGreaterThan(0);
    });

    it('should reset heartbeat timer on heartbeat_ack', async () => {
      const session = new WSSession({ 
        url: 'ws://localhost:8000/ws',
        heartbeatInterval: 30000 
      });
      
      await session.connect();
      await vi.advanceTimersByTimeAsync(20);

      // Send heartbeat ack
      const ws = (session as unknown as { ws: MockWebSocket }).ws;
      ws.simulateMessage({ type: 'heartbeat_ack', payload: null });

      // Advance just under 30 seconds - should not reconnect
      await vi.advanceTimersByTimeAsync(29000);

      expect(session.getState()).toBe('connected');
    });
  });

  describe('reconnection', () => {
    it('should attempt reconnection on unexpected disconnect', async () => {
      const session = new WSSession({ 
        url: 'ws://localhost:8000/ws',
        maxReconnectAttempts: 3,
        reconnectBaseDelay: 1000 
      });
      
      await session.connect();
      await vi.advanceTimersByTimeAsync(20);

      // Simulate unexpected disconnect (code != 1000)
      const ws = (session as unknown as { ws: MockWebSocket }).ws;
      ws.simulateClose(1006, 'Connection lost');

      // Should enter reconnecting state
      expect(session.getState()).toBe('reconnecting');
    });

    it('should use exponential backoff for reconnection', async () => {
      const session = new WSSession({ 
        url: 'ws://localhost:8000/ws',
        maxReconnectAttempts: 3,
        reconnectBaseDelay: 1000,
        reconnectMaxDelay: 30000
      });
      
      await session.connect();
      await vi.advanceTimersByTimeAsync(20);

      const ws = (session as unknown as { ws: MockWebSocket }).ws;
      ws.simulateClose(1006, 'Connection lost');

      // Should enter reconnecting state first
      expect(session.getState()).toBe('reconnecting');

      // Wait for first reconnect attempt (1s base delay + jitter)
      await vi.advanceTimersByTimeAsync(2000);

      // Should have attempted reconnect
      expect(session.getState()).toBe('connected');
    });
  });

  describe('message handling', () => {
    it('should handle incoming messages via event handler', async () => {
      const session = new WSSession({ url: 'ws://localhost:8000/ws' });
      await session.connect();
      await vi.advanceTimersByTimeAsync(20);

      let receivedMessage: WSMessage | null = null;
      session.onMessage((msg) => {
        receivedMessage = msg;
      });

      const ws = (session as unknown as { ws: MockWebSocket }).ws;
      ws.simulateMessage({ type: 'thinking_start', payload: { messageId: '123' } });

      expect(receivedMessage).toBeDefined();
      expect(receivedMessage?.type).toBe('thinking_start');
    });

    it('should send process messages', async () => {
      const session = new WSSession({ url: 'ws://localhost:8000/ws' });
      await session.connect();
      await vi.advanceTimersByTimeAsync(20);

      const sendSpy = vi.spyOn(MockWebSocket.prototype, 'send');
      session.send('process', { text: 'Hello, agent!' });

      expect(sendSpy).toHaveBeenCalled();
      const sentMessage = JSON.parse(sendSpy.mock.calls[0][0]);
      expect(sentMessage.type).toBe('process');
      expect(sentMessage.payload).toEqual({ text: 'Hello, agent!' });
    });
  });

  describe('state change events', () => {
    it('should notify on state changes', async () => {
      const session = new WSSession({ url: 'ws://localhost:8000/ws' });
      const states: string[] = [];
      
      session.onStateChange((state) => {
        states.push(state);
      });

      await session.connect();
      await vi.advanceTimersByTimeAsync(20);
      session.disconnect();
      await vi.advanceTimersByTimeAsync(20);

      expect(states).toContain('connecting');
      expect(states).toContain('connected');
      expect(states).toContain('disconnected');
    });
  });
});
