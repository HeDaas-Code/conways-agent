import { Plugin, WorkspaceLeaf } from 'obsidian';
import { AgentSidebar } from './sidebar';

export default class ConwaysAgentPlugin extends Plugin {
  sidebar: AgentSidebar | null = null;
  statusBar: HTMLElement | null = null;
  private sidebarLeaf: WorkspaceLeaf | null = null;

  async onload(): Promise<void> {
    this.addRibbonIcon('brain', "Conway's Agent", () => {
      this.toggleSidebar();
    });

    this.statusBar = this.addStatusBarItem();
    this.statusBar.setText('Agent: 启动中...');

    this.addCommand({
      id: 'open-agent-sidebar',
      name: 'Open Agent Sidebar',
      callback: () => this.toggleSidebar()
    });

    this.registerEvent(
      this.app.workspace.on('active-leaf-change', () => {
        this.updateStatusBar();
      })
    );

    // Initialize WS connection at plugin load
    this.injectStyles();
  }

  toggleSidebar(): void {
    const { workspace } = this.app;

    if (this.sidebarLeaf) {
      this.sidebarLeaf.detach();
      this.sidebarLeaf = null;
      this.sidebar = null;
      return;
    }

    this.sidebarLeaf = workspace.getRightLeaf(false);

    if (!this.sidebarLeaf) {
      return;
    }

    const container = (this.sidebarLeaf as unknown as { containerEl: HTMLElement }).containerEl;
    container.empty();

    this.sidebar = new AgentSidebar(container, this);
    this.sidebar.render();
  }

  private updateStatusBar(): void {
    if (!this.statusBar) return;

    const activeFile = this.app.workspace.getActiveFile();
    if (activeFile) {
      this.statusBar.setText(`Agent: 清醒 | ${activeFile.basename}`);
    } else {
      this.statusBar.setText('Agent: 清醒');
    }
  }

  private injectStyles(): void {
    const styleId = 'conways-agent-styles';
    if (document.getElementById(styleId)) return;

    const style = document.createElement('style');
    style.id = styleId;
    style.textContent = `
      .agent-sidebar-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 12px 16px;
        border-bottom: 1px solid var(--background-modifier-border);
        background: var(--background-secondary);
      }

      .agent-name {
        font-weight: 600;
        font-size: 14px;
        color: var(--text-normal);
      }

      .agent-status-indicator {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: var(--text-muted);
        transition: background 0.3s ease;
      }

      .agent-status-indicator[data-status="awake"] {
        background: #4ade80;
      }

      .agent-status-indicator[data-status="sleeping"] {
        background: #fbbf24;
        animation: pulse 1.5s ease-in-out infinite;
      }

      @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.5; }
      }

      .agent-messages-container {
        flex: 1;
        overflow-y: auto;
        padding: 16px;
        display: flex;
        flex-direction: column;
        gap: 12px;
      }

      .agent-message {
        display: flex;
        flex-direction: column;
        max-width: 85%;
        padding: 10px 14px;
        border-radius: 12px;
        font-size: 14px;
        line-height: 1.5;
      }

      .agent-message-user {
        align-self: flex-end;
        background: var(--interactive-accent);
        color: var(--text-on-accent);
        border-bottom-right-radius: 4px;
      }

      .agent-message-agent {
        align-self: flex-start;
        background: var(--background-secondary);
        color: var(--text-normal);
        border-bottom-left-radius: 4px;
      }

      .agent-message-content {
        white-space: pre-wrap;
        word-break: break-word;
      }

      .agent-message-time {
        font-size: 10px;
        opacity: 0.6;
        margin-top: 4px;
        align-self: flex-end;
      }

      .agent-input-area {
        padding: 12px 16px;
        border-top: 1px solid var(--background-modifier-border);
        background: var(--background-secondary);
        display: flex;
        gap: 8px;
        align-items: flex-end;
      }

      .agent-input {
        flex: 1;
        resize: none;
        border: 1px solid var(--background-modifier-border);
        border-radius: 8px;
        padding: 10px 12px;
        font-size: 14px;
        font-family: inherit;
        background: var(--background-primary);
        color: var(--text-normal);
        min-height: 44px;
        max-height: 120px;
      }

      .agent-input:focus {
        outline: none;
        border-color: var(--interactive-accent);
      }

      .agent-send-btn {
        padding: 10px 16px;
        border: none;
        border-radius: 8px;
        background: var(--interactive-accent);
        color: var(--text-on-accent);
        font-size: 14px;
        font-weight: 500;
        cursor: pointer;
        transition: opacity 0.2s ease;
      }

      .agent-send-btn:hover {
        opacity: 0.9;
      }

      .agent-send-btn:active {
        opacity: 0.8;
      }

      .agent-status-bar {
        padding: 6px 16px;
        font-size: 11px;
        color: var(--text-muted);
        background: var(--background-secondary);
        border-top: 1px solid var(--background-modifier-border);
      }
    `;

    document.head.appendChild(style);
  }

  onunload(): void {
    // Close sidebar and disconnect WebSocket
    if (this.sidebarLeaf) {
      this.sidebarLeaf.detach();
      this.sidebarLeaf = null;
    }

    if (this.sidebar) {
      this.sidebar.onUnload();
      this.sidebar = null;
    }

    const style = document.getElementById('conways-agent-styles');
    if (style) {
      style.remove();
    }
  }
}
