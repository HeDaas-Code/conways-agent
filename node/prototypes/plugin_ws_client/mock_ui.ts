/**
 * Mock UI for Obsidian Plugin WebSocket Client Prototype
 * 
 * Simulates DOM operations using console.log.
 * In production, these would directly manipulate Obsidian's DOM.
 */

import { StreamState, createInitialStreamState } from './message_parser';

// ─── Mock UI State ─────────────────────────────────────────────────────────

export interface UIState {
  connectionStatus: 'disconnected' | 'connecting' | 'connected' | 'reconnecting';
  streamState: StreamState;
  messageQueue: QueuedMessage[];
  errors: Error[];
}

export interface QueuedMessage {
  id: string;
  type: 'user' | 'agent';
  content: string;
  timestamp: Date;
}

export interface Error {
  code: string;
  message: string;
  timestamp: Date;
}

// ─── Mock UI Renderer ──────────────────────────────────────────────────────

export class MockUI {
  private state: UIState;
  private onUpdate: ((state: UIState) => void) | null = null;

  constructor() {
    this.state = {
      connectionStatus: 'disconnected',
      streamState: createInitialStreamState(),
      messageQueue: [],
      errors: [],
    };
  }

  // ─── Logger Interface (for processStreamingMessage) ───────────────────────

  log(category: string, message: string): void {
    const time = new Date().toLocaleTimeString('zh-CN', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      fractionalSecondDigits: 3,
    });
    console.log(`[${time}] [${category.padEnd(10)}] ${message}`);
  }

  // ─── State Access ─────────────────────────────────────────────────────────

  getState(): UIState {
    return { ...this.state };
  }

  setUpdateCallback(callback: (state: UIState) => void): void {
    this.onUpdate = callback;
  }

  // ─── Connection Status UI ─────────────────────────────────────────────────

  updateConnectionStatus(status: UIState['connectionStatus']): void {
    const statusIcons: Record<typeof status, string> = {
      disconnected: '⚪',
      connecting: '🟡',
      connected: '🟢',
      reconnecting: '🟠',
    };

    this.print('CONNECTION', `${statusIcons[status]} ${status.toUpperCase()}`);
    this.state.connectionStatus = status;
    this.notifyUpdate();
  }

  // ─── Message Queue UI ─────────────────────────────────────────────────────

  addUserMessage(content: string): string {
    const id = `user-${Date.now()}`;
    const message: QueuedMessage = {
      id,
      type: 'user',
      content,
      timestamp: new Date(),
    };

    this.print('USER MSG', `"${content.substring(0, 50)}${content.length > 50 ? '...' : ''}"`);
    this.state.messageQueue.push(message);
    this.notifyUpdate();
    return id;
  }

  addAgentMessage(content: string, thinking?: string): string {
    const id = `agent-${Date.now()}`;
    const message: QueuedMessage = {
      id,
      type: 'agent',
      content,
      timestamp: new Date(),
    };

    if (thinking) {
      this.print('AGENT MSG', `💭 "${thinking.substring(0, 30)}..." → 🤖 "${content.substring(0, 30)}..."`);
    } else {
      this.print('AGENT MSG', `"${content.substring(0, 50)}${content.length > 50 ? '...' : ''}"`);
    }
    this.state.messageQueue.push(message);
    this.notifyUpdate();
    return id;
  }

  getMessageQueue(): QueuedMessage[] {
    return [...this.state.messageQueue];
  }

  clearMessageQueue(): void {
    this.print('MESSAGES', 'Message queue cleared');
    this.state.messageQueue = [];
    this.notifyUpdate();
  }

  // ─── Streaming UI ──────────────────────────────────────────────────────────

  startThinking(messageId?: string): void {
    this.print('STREAM', '💭 Thinking started...');
    this.state.streamState = {
      ...this.state.streamState,
      isThinking: true,
      thinkingBuffer: '',
      messageId: messageId || null,
    };
    this.notifyUpdate();
  }

  updateThinking(chunk: string): void {
    const newBuffer = this.state.streamState.thinkingBuffer + chunk;
    this.print('STREAM', `💭 +"${chunk}"`);
    this.state.streamState = {
      ...this.state.streamState,
      thinkingBuffer: newBuffer,
    };
    this.notifyUpdate();
  }

  endThinking(): void {
    this.print('STREAM', '💭 Thinking ended');
    this.state.streamState = {
      ...this.state.streamState,
      isThinking: false,
      thinkingBuffer: '',
    };
    this.notifyUpdate();
  }

  updateResponse(chunk: string): void {
    const newBuffer = this.state.streamState.responseBuffer + chunk;
    this.print('STREAM', `🤖 +"${chunk}"`);
    this.state.streamState = {
      ...this.state.streamState,
      responseBuffer: newBuffer,
    };
    this.notifyUpdate();
  }

  endResponse(): void {
    const { responseBuffer } = this.state.streamState;
    this.print('STREAM', `🤖 Response complete (${responseBuffer.length} chars)`);
    
    // Move completed response to message queue
    if (responseBuffer) {
      this.addAgentMessage(responseBuffer, this.state.streamState.thinkingBuffer);
    }

    this.state.streamState = createInitialStreamState();
    this.notifyUpdate();
  }

  // ─── Error UI ─────────────────────────────────────────────────────────────

  showError(code: string, message: string): void {
    const error: Error = { code, message, timestamp: new Date() };
    this.print('ERROR', `❌ [${code}] ${message}`);
    this.state.errors.push(error);
    this.notifyUpdate();
  }

  clearErrors(): void {
    this.state.errors = [];
    this.notifyUpdate();
  }

  // ─── Status Bar UI ────────────────────────────────────────────────────────

  updateStatusBar(text: string): void {
    this.print('STATUS', text);
    this.notifyUpdate();
  }

  // ─── Private ───────────────────────────────────────────────────────────────

  private print(category: string, message: string): void {
    const time = new Date().toLocaleTimeString('zh-CN', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      fractionalSecondDigits: 3,
    });
    console.log(`[${time}] [${category.padEnd(10)}] ${message}`);
  }

  private notifyUpdate(): void {
    if (this.onUpdate) {
      this.onUpdate(this.state);
    }
  }
}

// ─── UI State Printer ──────────────────────────────────────────────────────

export function printUIState(ui: MockUI): void {
  const state = ui.getState();
  
  console.log('\n╔════════════════════════════════════════════════════════════╗');
  console.log('║                    UI STATE SNAPSHOT                      ║');
  console.log('╠════════════════════════════════════════════════════════════╣');
  
  // Connection Status
  const connIcon = {
    disconnected: '⚪',
    connecting: '🟡',
    connected: '🟢',
    reconnecting: '🟠',
  }[state.connectionStatus];
  console.log(`║ Connection:  ${connIcon} ${state.connectionStatus.padEnd(42)}║`);
  
  // Stream State
  console.log(`║ Thinking:    ${state.streamState.isThinking ? '💭 YES' : '❌ NO'.padEnd(43)}║`);
  if (state.streamState.thinkingBuffer) {
    const buffer = state.streamState.thinkingBuffer.substring(0, 35) + '...';
    console.log(`║   Buffer:    "${buffer}"`.padEnd(63) + '║');
  }
  if (state.streamState.responseBuffer) {
    const buffer = state.streamState.responseBuffer.substring(0, 35) + '...';
    console.log(`║   Response:  "${buffer}"`.padEnd(63) + '║');
  }
  
  // Message Queue
  console.log(`║ Messages:    ${state.messageQueue.length} queued`.padEnd(50) + '║');
  if (state.messageQueue.length > 0) {
    state.messageQueue.slice(-2).forEach(msg => {
      const prefix = msg.type === 'user' ? '👤' : '🤖';
      const content = msg.content.substring(0, 40) + (msg.content.length > 40 ? '...' : '');
      console.log(`║   ${prefix} "${content}"`.padEnd(62) + '║');
    });
  }
  
  // Errors
  console.log(`║ Errors:      ${state.errors.length}`.padEnd(50) + '║');
  if (state.errors.length > 0) {
    state.errors.slice(-1).forEach(err => {
      console.log(`║   ❌ [${err.code}] ${err.message.substring(0, 35)}...`.padEnd(63) + '║');
    });
  }
  
  console.log('╚════════════════════════════════════════════════════════════╝\n');
}
