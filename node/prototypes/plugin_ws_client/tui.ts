#!/usr/bin/env ts-node
/**
 * Terminal User Interface for Plugin WebSocket Client Prototype
 * 
 * Simulates the plugin behavior in an interactive TTY:
 * - [c] - Connect to WebSocket server
 * - [d] - Disconnect
 * - [m <text>] - Send user message
 * - [h] - Simulate heartbeat received
 * - [t chunk1|chunk2] - Simulate thinking chunks
 * - [r text] - Simulate response chunk
 * - [q] - Quit
 * 
 * Run: npx ts-node prototypes/plugin_ws_client/tui.ts
 */

import { WebSocket } from 'ws';
import { createInterface, Interface } from 'readline';
import { WSSession } from './ws_client';
import { MockUI, printUIState, UIState } from './mock_ui';
import { parse, processStreamingMessage, createInitialStreamState, StreamState } from './message_parser';
import { MockWSServer } from './mock_ws_server';

// ─── TUI State ─────────────────────────────────────────────────────────────

interface TUIState {
  session: WSSession | null;
  mockServer: MockWSServer | null;
  ui: MockUI;
  streamState: StreamState;
  running: boolean;
  serverMode: boolean;
}

let state: TUIState;

// ─── Main TUI ──────────────────────────────────────────────────────────────

function printBanner(): void {
  console.log(`
╔════════════════════════════════════════════════════════════════╗
║         Obsidian Plugin WebSocket Client Prototype            ║
╠════════════════════════════════════════════════════════════════╣
║  Commands:                                                     ║
║    [s]           Start mock WebSocket server                  ║
║    [c]           Connect to WebSocket server                  ║
║    [d]           Disconnect                                   ║
║    [m <text>]    Send user message                           ║
║    [h]           Simulate heartbeat received                  ║
║    [t chunk|...] Simulate thinking chunks                    ║
║    [r <text>]    Simulate response chunk                     ║
║    [e]           End response                                 ║
║    [p]           Print current state                          ║
║    [q]           Quit                                        ║
╠════════════════════════════════════════════════════════════════╣
║  Legend:                                                      ║
║    💭 = Thinking  |  🤖 = Response  |  ❌ = Error            ║
╚════════════════════════════════════════════════════════════════╝
  `);
}

function initState(): TUIState {
  const ui = new MockUI();
  
  return {
    session: null,
    mockServer: null,
    ui,
    streamState: createInitialStreamState(),
    running: true,
    serverMode: false,
  };
}

function handleCommand(input: string): boolean {
  const trimmed = input.trim();
  const parts = trimmed.split(/\s+(.*)/);
  const cmd = parts[0].toLowerCase();
  const args = parts[1] || '';

  switch (cmd) {
    // ─── Server Commands ──────────────────────────────────────────────────
    case 's':
      return handleStartServer();

    case 'x':
      return handleStopServer();

    // ─── Connection Commands ─────────────────────────────────────────────
    case 'c':
      return handleConnect();

    case 'd':
      return handleDisconnect();

    // ─── Message Commands ────────────────────────────────────────────────
    case 'm':
      return handleSendMessage(args);

    // ─── Simulation Commands ──────────────────────────────────────────────
    case 'h':
      return handleSimulateHeartbeat();

    case 't':
      return handleSimulateThinking(args);

    case 'r':
      return handleSimulateResponse(args);

    case 'e':
      return handleEndResponse();

    // ─── Utility Commands ─────────────────────────────────────────────────
    case 'p':
      printFullState();
      return true;

    case 'q':
      return handleQuit();

    case '':
      return true;

    default:
      state.ui.log('CMD', `Unknown command: ${cmd}. Type [p] to print state.`);
      return true;
  }
}

// ─── Command Handlers ───────────────────────────────────────────────────────

function handleStartServer(): boolean {
  if (state.mockServer) {
    state.ui.log('SERVER', 'Server already running');
    return true;
  }

  const port = 8080;
  state.mockServer = new MockWSServer(port);
  
  state.mockServer.start()
    .then(() => {
      state.serverMode = true;
      state.ui.log('SERVER', `🟢 Server started on ws://localhost:${port}`);
      state.ui.updateConnectionStatus('disconnected');
      printFullState();
    })
    .catch((err) => {
      state.ui.log('SERVER', `❌ Failed to start server: ${err.message}`);
      state.mockServer = null;
    });

  return true;
}

function handleStopServer(): boolean {
  if (!state.mockServer) {
    state.ui.log('SERVER', 'No server running');
    return true;
  }

  state.mockServer.stop();
  state.mockServer = null;
  state.serverMode = false;
  state.ui.log('SERVER', '⚪ Server stopped');
  return true;
}

function handleConnect(): boolean {
  const url = 'ws://localhost:8080';

  state.ui.log('CONNECT', `Connecting to ${url}...`);
  state.ui.updateConnectionStatus('connecting');

  state.session = new WSSession({ url });

  state.session.onStateChange((newState) => {
    const statusMap: Record<string, UIState['connectionStatus']> = {
      disconnected: 'disconnected',
      connecting: 'connecting',
      connected: 'connected',
      reconnecting: 'reconnecting',
    };
    state.ui.updateConnectionStatus(statusMap[newState] || 'disconnected');
    state.ui.log('STATE', `Connection state: ${newState}`);
  });

  state.session.onMessage((msg) => {
    state.streamState = processStreamingMessage(msg, state.streamState, state.ui);
  });

  state.session.onError((error) => {
    state.ui.showError('WS_ERROR', error.message);
  });

  state.session.connect()
    .then(() => {
      state.ui.log('CONNECT', '🟢 Connected successfully');
      printFullState();
    })
    .catch((err) => {
      state.ui.log('CONNECT', `❌ Connection failed: ${err.message}`);
      state.ui.updateConnectionStatus('disconnected');
      state.session = null;
    });

  return true;
}

function handleDisconnect(): boolean {
  if (!state.session) {
    state.ui.log('DISCONNECT', 'Not connected');
    return true;
  }

  state.session.disconnect();
  state.session = null;
  state.ui.log('DISCONNECT', '⚪ Disconnected');
  state.ui.updateConnectionStatus('disconnected');
  printFullState();
  return true;
}

function handleSendMessage(text: string): boolean {
  if (!text) {
    state.ui.log('MSG', 'Usage: [m <message text>]');
    return true;
  }

  if (!state.session) {
    state.ui.log('MSG', '❌ Not connected. Use [c] to connect first.');
    return true;
  }

  state.ui.addUserMessage(text);
  const sent = state.session.send('user_message', { message: text });

  if (sent) {
    state.ui.log('MSG', `📤 Sent: "${text.substring(0, 50)}${text.length > 50 ? '...' : ''}"`);
    state.streamState = { ...state.streamState, isThinking: true };
    state.ui.startThinking();
  } else {
    state.ui.log('MSG', '❌ Failed to send message');
  }

  printFullState();
  return true;
}

function handleSimulateHeartbeat(): boolean {
  state.ui.log('HEARTBEAT', '💓 Simulating heartbeat received from server');
  state.streamState = { ...state.streamState }; // Trigger update
  printFullState();
  return true;
}

function handleSimulateThinking(chunks: string): boolean {
  if (!chunks) {
    state.ui.log('SIM', 'Usage: [t chunk1|chunk2|chunk3]');
    return true;
  }

  const chunkList = chunks.split('|');
  state.ui.startThinking();

  chunkList.forEach((chunk, i) => {
    setTimeout(() => {
      state.streamState = processStreamingMessage(
        { type: 'thinking_chunk', payload: { chunk, index: i } },
        state.streamState,
        state.ui
      );
      printFullState();
    }, i * 400);
  });

  setTimeout(() => {
    state.streamState = processStreamingMessage(
      { type: 'thinking_end', payload: {} },
      state.streamState,
      state.ui
    );
    printFullState();
  }, chunkList.length * 400 + 200);

  return true;
}

function handleSimulateResponse(text: string): boolean {
  if (!text) {
    state.ui.log('SIM', 'Usage: [r <response text>]');
    return true;
  }

  const chunks = text.split(/(.{1,20})/g).filter(Boolean);
  
  chunks.forEach((chunk, i) => {
    setTimeout(() => {
      state.streamState = processStreamingMessage(
        { type: 'response_chunk', payload: { text: chunk } },
        state.streamState,
        state.ui
      );
      printFullState();
    }, i * 150);
  });

  return true;
}

function handleEndResponse(): boolean {
  state.streamState = processStreamingMessage(
    { type: 'response_end', payload: {} },
    state.streamState,
    state.ui
  );
  state.ui.endResponse();
  printFullState();
  return true;
}

function handleQuit(): boolean {
  state.ui.log('QUIT', 'Shutting down...');

  if (state.session) {
    state.session.disconnect();
    state.session = null;
  }

  if (state.mockServer) {
    state.mockServer.stop();
    state.mockServer = null;
  }

  state.running = false;
  state.ui.log('QUIT', '👋 Goodbye!');
  return false;
}

// ─── State Display ──────────────────────────────────────────────────────────

function printFullState(): void {
  console.log('\n' + '─'.repeat(64));
  printUIState(state.ui);

  // Session state
  if (state.session) {
    const snapshot = state.session.getStateSnapshot();
    console.log('─'.repeat(64));
    console.log('│ SESSION:');
    console.log(`│   State:         ${snapshot.state}`);
    console.log(`│   Reconnect:     ${snapshot.reconnectAttempts}/${snapshot.reconnectAttempts}`);
    console.log(`│   Last Pong:     ${Math.round(snapshot.lastPongAge / 1000)}s ago`);
    console.log('─'.repeat(64));
  }

  // Stream state
  console.log('│ STREAM:');
  console.log(`│   Thinking:      ${state.streamState.isThinking ? '💭 YES' : '❌ NO'}`);
  if (state.streamState.thinkingBuffer) {
    const buf = state.streamState.thinkingBuffer.substring(0, 50);
    console.log(`│   Thinking Buf:  "${buf}${state.streamState.thinkingBuffer.length > 50 ? '...' : ''}"`);
  }
  if (state.streamState.responseBuffer) {
    const buf = state.streamState.responseBuffer.substring(0, 50);
    console.log(`│   Response Buf:  "${buf}${state.streamState.responseBuffer.length > 50 ? '...' : ''}"`);
  }
  console.log('─'.repeat(64));
  console.log('');
}

// ─── Main Loop ─────────────────────────────────────────────────────────────

function runTUI(): void {
  state = initState();
  printBanner();

  const rl = createInterface({
    input: process.stdin,
    output: process.stdout,
    prompt: '> ',
  });

  rl.prompt();

  rl.on('line', (line: string) => {
    const shouldContinue = handleCommand(line);
    if (shouldContinue && state.running) {
      rl.prompt();
    } else {
      rl.close();
    }
  });

  rl.on('close', () => {
    console.log('\nTUI closed.');
    process.exit(0);
  });
}

// ─── Entry Point ────────────────────────────────────────────────────────────

runTUI();
