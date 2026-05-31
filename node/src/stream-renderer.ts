/**
 * Stream Renderer for Obsidian Plugin
 * 
 * Handles the state machine for streaming messages:
 * IDLE → THINKING → RESPONDING → COMPLETE
 */

import { WSMessage, isThinkingChunkPayload, isResponsePayload, isErrorPayload } from './ws-messages';

export type StreamState = 'idle' | 'thinking' | 'responding' | 'complete';

export interface StreamRenderContext {
  state: StreamState;
  thinkingBuffer: string;
  responseBuffer: string;
  messageId: string | null;
}

export interface StreamRendererConfig {
  onThinkingStart?: (messageId: string | null) => void;
  onThinkingChunk?: (chunk: string, buffer: string) => void;
  onThinkingDone?: (fullThinking: string) => void;
  onResponseChunk?: (chunk: string, buffer: string) => void;
  onResponseDone?: (fullResponse: string) => void;
  onError?: (code: string, message: string) => void;
  onStateChange?: (state: StreamState) => void;
}

const INITIAL_CONTEXT: StreamRenderContext = {
  state: 'idle',
  thinkingBuffer: '',
  responseBuffer: '',
  messageId: null,
};

export class StreamRenderer {
  private context: StreamRenderContext;
  private config: StreamRendererConfig;

  constructor(config: StreamRendererConfig = {}) {
    this.config = config;
    this.context = { ...INITIAL_CONTEXT };
  }

  /**
   * Process an incoming WSMessage and update the stream state.
   */
  processMessage(msg: WSMessage): void {
    const prevState = this.context.state;
    
    switch (msg.type) {
      case 'thinking_start':
        this.handleThinkingStart(msg);
        break;
      
      case 'thinking':
        if (isThinkingChunkPayload(msg.payload)) {
          this.handleThinkingChunk(msg.payload.chunk);
        }
        break;
      
      case 'thinking_done':
        this.handleThinkingDone();
        break;
      
      case 'response':
        if (isResponsePayload(msg.payload)) {
          this.handleResponseChunk(msg.payload.text);
        }
        break;
      
      case 'response_end':
        this.handleResponseDone();
        break;
      
      case 'thinking':
        // Legacy format - treat as response chunk
        if (isThinkingChunkPayload(msg.payload)) {
          this.handleResponseChunk(msg.payload.chunk);
        }
        break;
      
      case 'error':
        if (isErrorPayload(msg.payload)) {
          this.handleError(msg.payload.code, msg.payload.message);
        }
        break;
    }

    if (prevState !== this.context.state) {
      this.config.onStateChange?.(this.context.state);
    }
  }

  /**
   * Mark the current stream as complete and reset to idle.
   */
  complete(): void {
    // Emit final response if we have one
    if (this.context.responseBuffer) {
      this.config.onResponseDone?.(this.context.responseBuffer);
    }
    this.context = { ...INITIAL_CONTEXT };
    this.config.onStateChange?.('idle');
  }

  /**
   * Get the current stream context.
   */
  getContext(): StreamRenderContext {
    return { ...this.context };
  }

  /**
   * Get the current stream state.
   */
  getState(): StreamState {
    return this.context.state;
  }

  /**
   * Check if currently in a thinking phase.
   */
  isThinking(): boolean {
    return this.context.state === 'thinking';
  }

  /**
   * Check if currently receiving response.
   */
  isResponding(): boolean {
    return this.context.state === 'responding';
  }

  // ─── Private Handlers ─────────────────────────────────────────────────────

  private handleThinkingStart(msg: WSMessage): void {
    const payload = msg.payload as { messageId?: string } | null;
    this.context = {
      state: 'thinking',
      thinkingBuffer: '',
      responseBuffer: '',
      messageId: payload?.messageId ?? null,
    };
    this.config.onThinkingStart?.(this.context.messageId);
  }

  private handleThinkingChunk(chunk: string): void {
    this.context.thinkingBuffer += chunk;
    this.config.onThinkingChunk?.(chunk, this.context.thinkingBuffer);
  }

  private handleThinkingDone(): void {
    const fullThinking = this.context.thinkingBuffer;
    this.context = {
      ...this.context,
      state: 'responding',
      thinkingBuffer: '',
    };
    this.config.onThinkingDone?.(fullThinking);
  }

  private handleResponseChunk(text: string): void {
    // If we haven't transitioned to responding yet, do so
    if (this.context.state === 'thinking') {
      this.context.state = 'responding';
    }
    
    this.context.responseBuffer += text;
    this.config.onResponseChunk?.(text, this.context.responseBuffer);
  }

  private handleResponseDone(): void {
    const fullResponse = this.context.responseBuffer;
    this.context = { ...INITIAL_CONTEXT };
    this.config.onResponseDone?.(fullResponse);
    this.config.onStateChange?.('idle');
  }

  private handleError(code: string, message: string): void {
    this.config.onError?.(code, message);
    // Reset state on error
    this.context = { ...INITIAL_CONTEXT };
    this.config.onStateChange?.('idle');
  }
}

/**
 * Create a renderer bound to a sidebar element.
 */
export function createSidebarRenderer(
  container: HTMLElement
): StreamRenderer {
  let thinkingEl: HTMLElement | null = null;
  let responseEl: HTMLElement | null = null;

  return new StreamRenderer({
    onThinkingStart: () => {
      thinkingEl = container.createEl('div', { cls: 'agent-thinking' });
      thinkingEl.setText('💭 思考中...');
    },
    onThinkingChunk: (chunk, buffer) => {
      if (thinkingEl) {
        thinkingEl.setText(`💭 思考: ${buffer.slice(-200)}`);
      }
    },
    onThinkingDone: () => {
      if (thinkingEl) {
        thinkingEl.remove();
        thinkingEl = null;
      }
    },
    onResponseChunk: (chunk, buffer) => {
      if (!responseEl) {
        responseEl = container.createEl('div', { cls: 'agent-message agent-message-agent' });
      }
      responseEl.setText(buffer);
    },
    onResponseDone: () => {
      if (responseEl) {
        const time = new Date().toLocaleTimeString('zh-CN', {
          hour: '2-digit',
          minute: '2-digit'
        });
        responseEl.createEl('div', {
          cls: 'agent-message-time',
          text: time
        });
        responseEl = null;
      }
    },
    onError: (code, message) => {
      container.createEl('div', {
        cls: 'agent-error',
        text: `❌ 错误 [${code}]: ${message}`
      });
    },
  });
}
