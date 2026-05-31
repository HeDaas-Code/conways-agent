/**
 * Mock WebSocket Server for Prototype
 * 
 * Simulates the Python backend WebSocket server for testing.
 * Uses 'ws' npm package to create a real WebSocket server.
 */

import { WebSocketServer, WebSocket } from 'ws';
import { createInterface } from 'readline';
import * as readline from 'readline';

interface ServerMessage {
  type: string;
  payload: unknown;
  id?: string;
  timestamp?: number;
}

export class MockWSServer {
  private wss: WebSocketServer | null = null;
  private clients: Set<WebSocket> = new Set();
  private port: number;
  private heartbeatInterval: NodeJS.Timeout | null = null;
  private connected: boolean = false;

  // Message simulation state
  private simulatedThinking: string[] = [
    '正在分析你的问题',
    '思考中...',
    '查找相关上下文...',
    '构建回复...',
  ];
  private simulatedResponse: string = '';

  constructor(port: number = 8080) {
    this.port = port;
  }

  start(): Promise<void> {
    return new Promise((resolve, reject) => {
      try {
        this.wss = new WebSocketServer({ port: this.port });
        this.connected = true;

        this.wss.on('listening', () => {
          console.log(`[MOCK SERVER] Listening on ws://localhost:${this.port}`);
          this.startHeartbeat();
          resolve();
        });

        this.wss.on('connection', (ws: WebSocket) => {
          this.clients.add(ws);
          console.log(`[MOCK SERVER] Client connected (${this.clients.size} total)`);

          ws.on('message', (data) => {
            this.handleMessage(ws, data);
          });

          ws.on('close', () => {
            this.clients.delete(ws);
            console.log(`[MOCK SERVER] Client disconnected (${this.clients.size} remaining)`);
          });

          ws.on('error', (error) => {
            console.error('[MOCK SERVER] Client error:', error);
            this.clients.delete(ws);
          });

          ws.on('pong', () => {
            console.log('[MOCK SERVER] Received client pong');
          });

          // Send welcome message
          this.send(ws, 'system', { message: 'Connected to mock server' });
        });

        this.wss.on('error', (error) => {
          console.error('[MOCK SERVER] Server error:', error);
          this.connected = false;
          reject(error);
        });

      } catch (error) {
        this.connected = false;
        reject(error);
      }
    });
  }

  stop(): void {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }

    if (this.wss) {
      this.clients.forEach(client => {
        client.close(1000, 'Server shutting down');
      });
      this.wss.close();
      this.wss = null;
    }
    this.connected = false;
    this.clients.clear();
    console.log('[MOCK SERVER] Server stopped');
  }

  isConnected(): boolean {
    return this.connected;
  }

  getClientCount(): number {
    return this.clients.size;
  }

  // ─── Message Handlers ─────────────────────────────────────────────────────

  private handleMessage(ws: WebSocket, data: unknown): void {
    try {
      let parsed: ServerMessage;
      if (typeof data === 'string') {
        parsed = JSON.parse(data);
      } else if (Buffer.isBuffer(data)) {
        parsed = JSON.parse(data.toString());
      } else {
        parsed = JSON.parse(String(data));
      }

      console.log(`[MOCK SERVER] Received: ${parsed.type}`);

      switch (parsed.type) {
        case 'ping':
          this.send(ws, 'pong', { ts: Date.now() });
          break;

        case 'user_message':
          this.simulateStream(ws, parsed.payload as { message: string });
          break;

        default:
          console.log(`[MOCK SERVER] Unknown message type: ${parsed.type}`);
      }
    } catch (error) {
      console.error('[MOCK SERVER] Failed to parse message:', error);
    }
  }

  private send(ws: WebSocket, type: string, payload: unknown): void {
    if (ws.readyState === WebSocket.OPEN) {
      const msg: ServerMessage = {
        type,
        payload,
        timestamp: Date.now(),
      };
      ws.send(JSON.stringify(msg));
    }
  }

  private broadcast(type: string, payload: unknown): void {
    const msg: ServerMessage = {
      type,
      payload,
      timestamp: Date.now(),
    };
    const data = JSON.stringify(msg);

    this.clients.forEach(client => {
      if (client.readyState === WebSocket.OPEN) {
        client.send(data);
      }
    });
  }

  // ─── Heartbeat ────────────────────────────────────────────────────────────

  private startHeartbeat(): void {
    this.heartbeatInterval = setInterval(() => {
      this.clients.forEach(client => {
        if (client.readyState === WebSocket.OPEN) {
          client.ping();
        }
      });
    }, 30000);
  }

  // ─── Stream Simulation ────────────────────────────────────────────────────

  private simulateStream(ws: WebSocket, payload: { message: string }): void {
    const messageId = `msg-${Date.now()}`;

    // Simulate thinking chunks
    let thinkingIndex = 0;
    const thinkingInterval = setInterval(() => {
      if (thinkingIndex < this.simulatedThinking.length) {
        this.send(ws, 'thinking_chunk', { 
          chunk: this.simulatedThinking[thinkingIndex],
          index: thinkingIndex,
        });
        thinkingIndex++;
      } else {
        clearInterval(thinkingInterval);
        this.send(ws, 'thinking_end', { messageId });
        
        // Start response simulation
        this.simulateResponse(ws, payload.message, messageId);
      }
    }, 500);
  }

  private simulateResponse(ws: WebSocket, userMessage: string, messageId: string): void {
    const responses = [
      `我收到了你的消息: "${userMessage}"`,
      '这是模拟的流式响应。',
      '在实际部署中，这里会是来自 AI 的真实回复。',
      '响应结束。',
    ];

    let responseIndex = 0;
    const responseInterval = setInterval(() => {
      if (responseIndex < responses.length) {
        this.send(ws, 'response_chunk', { 
          text: responses[responseIndex] + '\n',
          messageId,
        });
        responseIndex++;
      } else {
        clearInterval(responseInterval);
        this.send(ws, 'response_end', { messageId });
      }
    }, 400);
  }

  // ─── External Control ─────────────────────────────────────────────────────

  /**
   * Send a specific message to all connected clients (for TUI control)
   */
  sendToClients(type: string, payload: unknown): void {
    this.broadcast(type, payload);
  }

  /**
   * Simulate heartbeat response (for TUI testing)
   */
  simulateHeartbeat(): void {
    console.log('[MOCK SERVER] Simulating heartbeat...');
    this.broadcast('pong', { ts: Date.now() });
  }

  /**
   * Simulate thinking chunk (for TUI testing)
   */
  simulateThinkingChunk(chunks: string[]): void {
    console.log('[MOCK SERVER] Simulating thinking chunks...');
    chunks.forEach((chunk, i) => {
      setTimeout(() => {
        this.broadcast('thinking_chunk', { chunk, index: i });
      }, i * 300);
    });
    setTimeout(() => {
      this.broadcast('thinking_end', {});
    }, chunks.length * 300);
  }

  /**
   * Simulate response (for TUI testing)
   */
  simulateResponseChunk(text: string): void {
    console.log('[MOCK SERVER] Simulating response...');
    this.broadcast('response_chunk', { text });
  }

  simulateResponseEnd(): void {
    this.broadcast('response_end', {});
  }
}

// ─── CLI Server Controller ─────────────────────────────────────────────────

export class MockServerController {
  private server: MockWSServer;
  private rl: readline.Interface;

  constructor(server: MockWSServer) {
    this.server = server;
    this.rl = createInterface({
      input: process.stdin,
      output: process.stdout,
    });
  }

  async start(): Promise<void> {
    await this.server.start();
    console.log('\n[MOCK SERVER] Type commands:');
    console.log('  [t chunk1|chunk2|...] - Simulate thinking');
    console.log('  [r text] - Simulate response');
    console.log('  [h] - Simulate heartbeat');
    console.log('  [q] - Quit server\n');
  }

  handleInput(input: string): boolean {
    const trimmed = input.trim();
    
    if (trimmed === 'q') {
      this.server.stop();
      this.rl.close();
      return false;
    }

    if (trimmed.startsWith('t ')) {
      const chunks = trimmed.slice(2).split('|');
      this.server.simulateThinkingChunk(chunks);
    } else if (trimmed.startsWith('r ')) {
      const text = trimmed.slice(2);
      this.server.simulateResponseChunk(text);
    } else if (trimmed === 'h') {
      this.server.simulateHeartbeat();
    } else if (trimmed === 'end') {
      this.server.simulateResponseEnd();
    }

    return true;
  }
}
