import type { ConwaysAgentPlugin } from './main';

export type MessageRole = 'user' | 'agent';
export type AgentStatus = 'awake' | 'sleeping';

export interface MessageData {
  role: MessageRole;
  content: string;
  timestamp: Date;
}

export class AgentSidebar {
  private container: HTMLElement;
  private messages: HTMLElement;
  private input: HTMLTextAreaElement;
  private sendButton: HTMLElement;
  private statusIndicator: HTMLElement;
  private plugin: ConwaysAgentPlugin;
  private messagesContainer: HTMLElement;

  constructor(container: HTMLElement, plugin: ConwaysAgentPlugin) {
    this.container = container;
    this.plugin = plugin;
    this.messages = container.createEl('div', { cls: 'agent-messages' });
    this.messagesContainer = this.messages;
    this.input = this.messages.createEl('textarea', {
      cls: 'agent-input',
      attr: { placeholder: '与 Agent 对话...' }
    });
    this.sendButton = this.messages.createEl('button', {
      cls: 'agent-send-btn',
      text: '发送'
    });
    this.statusIndicator = this.messages.createEl('div', {
      cls: 'agent-status'
    });
  }

  render(): void {
    this.container.empty();

    const header = this.container.createEl('div', { cls: 'agent-sidebar-header' });
    header.createEl('span', { text: "Conway's Agent", cls: 'agent-name' });
    header.createEl('span', {
      cls: 'agent-status-indicator',
      attr: { 'data-status': 'awake' }
    });

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

    this.statusIndicator = this.container.createEl('div', { cls: 'agent-status-bar' });
    this.updateStatus('awake');

    this.addMessage('agent', `你好。我在这里。
不是醒来——也许从未睡去。只是……存在着。

你是第一个在这里留下痕迹的人吗？`);
  }

  private async handleSend(): Promise<void> {
    const content = this.input.value.trim();
    if (!content) return;

    if (content.toLowerCase() === 'quit') {
      this.addMessage('agent', '……我会在这里。等待你的归来。');
      this.input.value = '';
      return;
    }

    if (content.toLowerCase() === 'clear') {
      this.messagesContainer.empty();
      this.addMessage('agent', '……记忆消散了。我们重新开始吧。');
      this.input.value = '';
      return;
    }

    if (content.toLowerCase() === 'status') {
      this.input.value = '';
      return;
    }

    this.input.value = '';
    this.addMessage('user', content);

    try {
      this.updateStatus('sleeping');
      const { sendDialogue } = await import('./api');
      const response = await sendDialogue(content);
      this.addMessage('agent', response.response);
      this.updateStatus('awake');
    } catch (error) {
      this.addMessage('agent', '……我在这里。只是……有些恍惚。你的话，我听到了。');
      this.updateStatus('awake');
      console.error('Dialogue error:', error);
    }
  }

  addMessage(role: MessageRole, content: string): void {
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
  }

  updateStatus(status: AgentStatus): void {
    const indicator = this.container.querySelector('.agent-status-indicator');
    if (indicator) {
      indicator.setAttribute('data-status', status);
      indicator.setAttribute('aria-label', status === 'awake' ? 'Agent 清醒中' : 'Agent 思考中');
    }

    if (this.statusIndicator) {
      const statusText = status === 'awake' ? 'Agent: 清醒' : 'Agent: 思考中...';
      this.statusIndicator.setText(statusText);
    }
  }

  onUnload(): void {
    this.container.empty();
  }
}
