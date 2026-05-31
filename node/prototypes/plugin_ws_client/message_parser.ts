/**
 * Message Parser for Obsidian Plugin WebSocket Client
 * 
 * PROTOYPE - answers: How to parse WS messages and map them to UI updates?
 */

import { WSMessage } from './ws_client';

export interface ParsedThinkingChunk {
  chunkIndex: number;
  content: string;
  isFinal: boolean;
}

export interface ParsedResponse {
  content: string;
  isComplete: boolean;
  messageId?: string;
}

export interface StreamState {
  thinkingBuffer: string;
  responseBuffer: string;
  isThinking: boolean;
  messageId: string | null;
}

// ─── Message Types ─────────────────────────────────────────────────────────

export type IncomingMessageType = 
  | 'thinking_start'
  | 'thinking_chunk'
  | 'thinking_end'
  | 'response_chunk'
  | 'response_end'
  | 'error'
  | 'pong'
  | 'heartbeat';

export interface ThinkingChunkPayload {
  chunk: string;
  index?: number;
}

export interface ResponseChunkPayload {
  text: string;
  messageId?: string;
}

export interface ErrorPayload {
  code: string;
  message: string;
}

// ─── Parser Functions ──────────────────────────────────────────────────────

/**
 * Parse raw WebSocket message into structured format
 */
export function parse(raw: unknown): WSMessage | null {
  if (typeof raw === 'string') {
    try {
      return JSON.parse(raw) as WSMessage;
    } catch {
      return null;
    }
  }
  
  if (Buffer.isBuffer(raw)) {
    try {
      return JSON.parse(raw.toString()) as WSMessage;
    } catch {
      return null;
    }
  }

  return null;
}

/**
 * Get the message type from a parsed message
 */
export function getMessageType(msg: WSMessage): IncomingMessageType | null {
  return msg.type as IncomingMessageType;
}

// ─── Logger Interface ───────────────────────────────────────────────────────

/**
 * Simple logger interface for message rendering
 */
export interface Logger {
  log(type: string, message: string): void;
}

// ─── UI Rendering Functions (mock DOM operations) ──────────────────────────

/**
 * Render typing indicator for thinking chunks (typewriter effect simulation)
 * In production: updates DOM element with incremental content
 */
export function renderThinkingChunk(
  logger: Logger,
  content: string,
  isNew: boolean = false
): void {
  if (isNew) {
    logger.log('💭 [THINKING]', `Started thinking: "${content.substring(0, 30)}..."`);
  } else {
    logger.log('💭 [THINKING]', `Continue: "${content.substring(0, 30)}..."`);
  }
}

/**
 * Clear thinking indicator when thinking ends
 */
export function clearThinkingIndicator(logger: Logger): void {
  logger.log('💭 [THINKING]', 'Thinking complete ✓');
}

/**
 * Render response chunk with typewriter effect
 */
export function renderResponseChunk(
  logger: Logger,
  content: string,
  isNew: boolean = false
): void {
  if (isNew) {
    logger.log('🤖 [RESPONSE]', `New response: "${content.substring(0, 50)}..."`);
  } else {
    logger.log('🤖 [RESPONSE]', `Append: "${content.substring(0, 30)}..."`);
  }
}

/**
 * Render final complete response
 */
export function renderFinalResponse(logger: Logger, content: string): void {
  logger.log('🤖 [RESPONSE]', `Complete (${content.length} chars): "${content.substring(0, 80)}..."`);
}

// ─── Mock DOM for Prototype ─────────────────────────────────────────────────

export class MockDOM {
  private logs: Array<{ type: string; message: string; timestamp: Date }> = [];
  private elements: Map<string, HTMLElementMock> = new Map();

  constructor(public containerId: string = 'mock-container') {}

  log(type: string, message: string): void {
    const entry = {
      type,
      message,
      timestamp: new Date(),
    };
    this.logs.push(entry);
    
    // Simulate console output
    const time = entry.timestamp.toLocaleTimeString('zh-CN', { 
      hour: '2-digit', 
      minute: '2-digit',
      second: '2-digit'
    });
    console.log(`[${time}] ${type} ${message}`);
  }

  getLogs(): typeof this.logs {
    return [...this.logs];
  }

  // Mock DOM element creation
  createElement(tag: string, _options?: { cls?: string; text?: string }): HTMLElementMock {
    const el = new HTMLElementMock(tag);
    this.elements.set(`${tag}-${Date.now()}`, el);
    return el;
  }

  querySelector(_selector: string): HTMLElementMock | null {
    return null; // Simplified for prototype
  }

  // Simulate sidebar message update
  updateMessage(role: 'user' | 'agent', content: string): void {
    const icon = role === 'user' ? '👤' : '🤖';
    this.log(icon, `[${role.toUpperCase()}] ${content}`);
  }
}

class HTMLElementMock {
  private children: HTMLElementMock[] = [];
  private text: string = '';
  private attributes: Map<string, string> = new Map();

  constructor(private tag: string) {}

  createEl(tag: string, options?: { cls?: string; text?: string; attr?: Record<string, string> }): HTMLElementMock {
    const el = new HTMLElementMock(tag);
    if (options?.cls) el.setAttribute('class', options.cls);
    if (options?.text) el.setText(options.text);
    if (options?.attr) {
      Object.entries(options.attr).forEach(([k, v]) => el.setAttribute(k, v));
    }
    this.children.push(el);
    return el;
  }

  setText(text: string): void {
    this.text = text;
  }

  get textContent(): string {
    return this.text + this.children.map(c => c.textContent).join('');
  }

  setAttribute(name: string, value: string): void {
    this.attributes.set(name, value);
  }

  getAttribute(name: string): string | null {
    return this.attributes.get(name) || null;
  }

  addEventListener(_event: string, _handler: () => void): void {
    // Mock - no-op
  }
}

// ─── Stream State Machine ────────────────────────────────────────────────────

/**
 * Process streaming message and update state
 */
export function processStreamingMessage(
  msg: WSMessage,
  state: StreamState,
  logger: Logger
): StreamState {
  switch (msg.type) {
    case 'thinking_start':
      return {
        ...state,
        isThinking: true,
        thinkingBuffer: '',
        messageId: (msg.payload as { messageId?: string })?.messageId || state.messageId,
      };

    case 'thinking_chunk': {
      const { chunk } = msg.payload as ThinkingChunkPayload;
      const newBuffer = state.thinkingBuffer + chunk;
      renderThinkingChunk(logger, newBuffer, state.thinkingBuffer === '');
      return {
        ...state,
        thinkingBuffer: newBuffer,
      };
    }

    case 'thinking_end':
      clearThinkingIndicator(logger);
      return {
        ...state,
        isThinking: false,
        thinkingBuffer: '',
      };

    case 'response_chunk': {
      const { text } = msg.payload as ResponseChunkPayload;
      const newBuffer = state.responseBuffer + text;
      renderResponseChunk(logger, text, state.responseBuffer === '');
      return {
        ...state,
        responseBuffer: newBuffer,
      };
    }

    case 'response_end':
      renderFinalResponse(logger, state.responseBuffer);
      return {
        thinkingBuffer: '',
        responseBuffer: '',
        isThinking: false,
        messageId: null,
      };

    case 'error': {
      const error = msg.payload as ErrorPayload;
      logger.log('❌ [ERROR]', `${error.code}: ${error.message}`);
      return state;
    }

    default:
      return state;
  }
}

/**
 * Create initial stream state
 */
export function createInitialStreamState(): StreamState {
  return {
    thinkingBuffer: '',
    responseBuffer: '',
    isThinking: false,
    messageId: null,
  };
}
