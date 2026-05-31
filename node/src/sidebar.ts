import type ConwaysAgentPlugin from './main';
import { WSSession } from './ws-client';
import { StreamRenderer } from './stream-renderer';

export type MessageRole = 'user' | 'agent';
export type AgentStatus = 'awake' | 'sleeping' | 'connecting' | 'reconnecting' | 'disconnected';

export interface MessageData {
  role: MessageRole;
  content: string;
  timestamp: Date;
}

export class AgentSidebar {
  private container: HTMLElement;
  private messages!: HTMLElement;
  private input!: HTMLTextAreaElement;
  private sendButton!: HTMLElement;
  private statusIndicator!: HTMLElement;
  private plugin: ConwaysAgentPlugin;
  private messagesContainer!: HTMLElement;

  // WebSocket session
  private session: WSSession | null = null;
  private streamRenderer: StreamRenderer | null = null;
  private currentResponseEl: HTMLElement | null = null;

  // Message history for display
  private messageHistory: MessageData[] = [];

  constructor(container: HTMLElement, plugin: ConwaysAgentPlugin) {
    this.container = container;
    this.plugin = plugin;
  }

  // ─── Public API ───────────────────────────────────────────────────────────

  async initialize(): Promise<void> {
    // Create WebSocket session
    const wsUrl = this.getWsUrl();
    this.session = new WSSession({
      url: wsUrl,
      heartbeatInterval: 30000,
      maxReconnectAttempts: 5,
      reconnectBaseDelay: 1000,
      reconnectMaxDelay: 30000,
    });

    // Set up event handlers
    this.session.onStateChange((state) => {
      this.updateStatusFromConnectionState(state);
    });

    this.session.onMessage((msg) => {
      this.handleServerMessage(msg);
    });

    this.session.onError((error) => {
      console.error('WS Error:', error);
    });

    // Connect
    try {
      await this.session.connect();
    } catch (error) {
      console.error('Failed to connect:', error);
    }
  }

  render(): void {
    this.container.empty();

    const header = this.container.createEl('div', { cls: 'agent-sidebar-header' });
    header.createEl('span', { text: "Conway's Agent", cls: 'agent-name' });
    
    const statusDot = header.createEl('span', {
      cls: 'agent-status-indicator',
      attr: { 'data-status': 'disconnected' }
    });
    this.statusIndicator = statusDot;

    this.messagesContainer = this.container.createEl('div', { cls: 'agent-messages-container' });
    this.messages = this.messagesContainer;

    const inputArea = this.container.createEl('div', { cls: 'agent-input-area' });
    this.input = inputArea.createEl('textarea', {
      cls: 'agent-input',
      attr: {
        placeholder: '与 Agent 对话...',
        rows: '3'
      }
    });

    this.sendButton = inputArea.createEl('button', {
      cls: 'agent-send-btn',
      text: '发送'
    });
    this.sendButton.addEventListener('click', () => this.handleSend());

    this.input.addEventListener('keydown', (e: KeyboardEvent) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        this.handleSend();
      }
    });

    const statusBar = this.container.createEl('div', { cls: 'agent-status-bar' });
    statusBar.setText('Agent: 连接中...');

    // Initialize WebSocket connection
    this.initialize();
  }

  // ─── Message Handlers ─────────────────────────────────────────────────────

  private handleSend(): void {
    const content = this.input.value.trim();
    if (!content) return;

    if (content.toLowerCase() === 'quit') {
      this.addMessage('agent', '……我会在这里。等待你的归来。');
      this.input.value = '';
      return;
    }

    if (content.toLowerCase() === 'clear') {
      this.messagesContainer.empty();
      this.messageHistory = [];
      this.addMessage('agent', '……记忆消散了。我们重新开始吧。');
      this.input.value = '';
      return;
    }

    if (content.toLowerCase() === 'status') {
      this.input.value = '';
      if (this.session) {
        const snapshot = this.session.getStateSnapshot();
        this.addMessage('agent', `连接状态: ${snapshot.state}`);
      }
      return;
    }

    this.input.value = '';
    this.addMessage('user', content);

    // Send via WebSocket
    if (this.session && this.session.getState() === 'connected') {
      this.session.send('process', { text: content });
      this.updateStatus('sleeping');
    } else {
      this.addMessage('agent', '……连接似乎断开了。');
    }
  }

  private handleServerMessage(msg: { type: string; payload: unknown }): void {
    switch (msg.type) {
      case 'thinking_start':
        this.startThinking();
        break;
      
      case 'thinking':
        this.appendThinking(msg.payload as { chunk: string });
        break;
      
      case 'thinking_done':
        this.endThinking();
        break;
      
      case 'response':
        this.appendResponse(msg.payload as { text: string });
        break;
      
      case 'response_end':
        this.completeResponse();
        break;
      
      case 'error':
        this.showError(msg.payload as { code: string; message: string });
        break;
    }
  }

  // ─── Stream Rendering ─────────────────────────────────────────────────────

  private startThinking(): void {
    this.updateStatus('sleeping');
    // Thinking is shown in the agent response element
  }

  private appendThinking(payload: { chunk: string }): void {
    // Append thinking indicator to current message or create one
    if (!this.currentResponseEl) {
      this.currentResponseEl = this.createAgentMessage();
    }
    const thinkingEl = this.currentResponseEl.querySelector('.agent-thinking') || 
      this.currentResponseEl.createEl('div', { cls: 'agent-thinking' });
    thinkingEl.setText(`💭 ${payload.chunk}`);
  }

  private endThinking(): void {
    // Remove thinking indicator
    if (this.currentResponseEl) {
      const thinkingEl = this.currentResponseEl.querySelector('.agent-thinking');
      if (thinkingEl) {
        thinkingEl.remove();
      }
    }
  }

  private appendResponse(payload: { text: string }): void {
    if (!this.currentResponseEl) {
      this.currentResponseEl = this.createAgentMessage();
    }
    const contentEl = this.currentResponseEl.querySelector('.agent-message-content') || 
      this.currentResponseEl.createEl('div', { cls: 'agent-message-content' });
    contentEl.setText((contentEl.textContent || '') + payload.text);
    this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
  }

  private completeResponse(): void {
    if (this.currentResponseEl) {
      const time = new Date().toLocaleTimeString('zh-CN', {
        hour: '2-digit',
        minute: '2-digit'
      });
      this.currentResponseEl.createEl('div', {
        cls: 'agent-message-time',
        text: time
      });
      this.currentResponseEl = null;
    }
    this.updateStatus('awake');
  }

  private showError(payload: { code: string; message: string }): void {
    this.createAgentMessage(payload.message, 'error');
    this.updateStatus('awake');
    this.currentResponseEl = null;
  }

  // ─── UI Helpers ───────────────────────────────────────────────────────────

  private createAgentMessage(content: string = '', type: 'normal' | 'error' = 'normal'): HTMLElement {
    const messageEl = this.messages.createEl('div', { 
      cls: `agent-message agent-message-agent${type === 'error' ? ' agent-message-error' : ''}` 
    });

    if (type === 'error') {
      messageEl.createEl('div', { cls: 'agent-message-content', text: content });
    }

    this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
    return messageEl;
  }

  private addMessage(role: MessageRole, content: string): void {
    const messageEl = this.messages.createEl('div', { cls: `agent-message agent-message-${role}` });

    const time = new Date().toLocaleTimeString('zh-CN', {
      hour: '2-digit',
      minute: '2-digit'
    });

    messageEl.createEl('div', {
      cls: 'agent-message-content',
      text: content
    });

    messageEl.createEl('div', {
      cls: 'agent-message-time',
      text: time
    });

    this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
    this.messageHistory.push({ role, content, timestamp: new Date() });
  }

  private updateStatus(status: AgentStatus): void {
    const statusMap: Record<AgentStatus, string> = {
      awake: 'awake',
      sleeping: 'sleeping',
      connecting: 'connecting',
      reconnecting: 'reconnecting',
      disconnected: 'disconnected',
    };

    const statusDot = this.container.querySelector('.agent-status-indicator');
    if (statusDot) {
      statusDot.setAttribute('data-status', statusMap[status]);
    }

    const statusBar = this.container.querySelector('.agent-status-bar');
    if (statusBar) {
      const statusText: Record<AgentStatus, string> = {
        awake: 'Agent: 清醒',
        sleeping: 'Agent: 思考中...',
        connecting: 'Agent: 连接中...',
        reconnecting: 'Agent: 重新连接中...',
        disconnected: 'Agent: 离线',
      };
      statusBar.setText(statusText[status]);
    }
  }

  private updateStatusFromConnectionState(state: string): void {
    const statusMap: Record<string, AgentStatus> = {
      connected: 'awake',
      connecting: 'connecting',
      reconnecting: 'reconnecting',
      disconnected: 'disconnected',
    };
    this.updateStatus(statusMap[state] || 'disconnected');
  }

  private getWsUrl(): string {
    // Use environment variable or default
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    return `${protocol}//${host}/ws`;
  }

  onUnload(): void {
    if (this.session) {
      this.session.disconnect();
      this.session = null;
    }
    this.container.empty();
  }
}
