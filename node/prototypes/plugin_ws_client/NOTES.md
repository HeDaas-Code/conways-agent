# Obsidian Plugin WebSocket Client Prototype - Design Notes

## Question Being Answered

> How to handle connection management, heartbeat, streaming messages, and auto-reconnect in a browser environment for an Obsidian plugin?

---

## 1. Heartbeat Strategy

### Decision: **Client-Driven Ping + Server Acknowledgment**

```
Client ──── ping ────► Server (every 30s)
Client ◄─── pong ──── Server
```

### Key Design Points

| Aspect | Value | Rationale |
|--------|-------|-----------|
| Client ping interval | 30s | Half of server's 60s timeout |
| Heartbeat timeout | 60s | Server-side disconnect threshold |
| Ping method | `ws.ping()` + message | Browser WS ping unreliable; message backup |

### Browser Feasibility: ✅ YES

- `WebSocket.ping()` works in browsers (Obsidian/Electron)
- Fallback to application-level ping message
- Track `lastPong` timestamp client-side
- If `Date.now() - lastPong > 60000`, trigger reconnect

### Alternative Considered
- **Server-driven heartbeat**: Server sends pings to client
  - ❌ Less reliable across proxies/load balancers
  - ❌ Requires server timeout configuration alignment

---

## 2. Reconnection Strategy

### Decision: **Automatic Exponential Backoff with User Override**

```
Disconnect
    │
    ▼
Check: client-initiated? (code 1000)
    │
    ├─ YES → Don't reconnect, stay disconnected
    │
    └─ NO → Schedule reconnect with backoff
                │
                ▼
            attempt = 0
            delay = 1000ms * 2^attempt + jitter
            │
            ▼
        delay < maxDelay (30s)?
            │
            ├─ YES → connect(), increment attempt
            │
            └─ NO → stop, stay disconnected
```

### Key Design Points

| Aspect | Value | Rationale |
|--------|-------|-----------|
| Max attempts | 5 | Prevent infinite reconnect loops |
| Base delay | 1000ms | Minimum wait between attempts |
| Max delay | 30000ms (30s) | Cap to avoid user waiting forever |
| Jitter | 0-1000ms random | Prevent thundering herd on shared servers |

### User Override

- `disconnect()` sets `reconnectAttempts = maxReconnectAttempts`
- This prevents auto-reconnect when user intentionally disconnects
- UI should expose "Disconnect" vs "Reconnecting..." clearly

### Browser Feasibility: ✅ YES

- `setTimeout` / `setInterval` work in browser
- Exponential backoff is standard practice
- Need to handle "page hidden" → reduce reconnect frequency

---

## 3. Message to UI Mapping

### Stream State Machine

```
                    ┌──────────────┐
                    │   IDLE      │
                    └──────┬───────┘
                           │ thinking_start
                           ▼
                    ┌──────────────┐
              ┌────►│   THINKING   │◄────┐
              │     └──────┬───────┘     │
              │            │             │
              │   thinking_chunk         │ (error)
              │            │             │
              │            ▼             │
              │     ┌──────────────┐     │
              │     │  APPENDING   │─────┘
              │     │  (thinking)  │
              │     └──────┬───────┘
              │            │ thinking_end
              │            ▼
              │     ┌──────────────┐
              └─────│   RESPONDING │◄────┌ response_chunk
                    └──────┬───────┘     │
                           │             │
                           │ response_end│
                           │             │
                           ▼             │
                    ┌──────────────┐     │
                    │   COMPLETE   │─────┘
                    └──────────────┘
```

### Message Types → UI Actions

| WS Message Type | UI Action |
|-----------------|-----------|
| `thinking_start` | Show thinking indicator, clear buffers |
| `thinking_chunk` | Append to thinking buffer, typewriter render |
| `thinking_end` | Hide thinking indicator |
| `response_chunk` | Append to response buffer, typewriter render |
| `response_end` | Move response to message queue, reset buffers |
| `error` | Show error toast, reset stream state |

### Browser Feasibility: ✅ YES

- Obsidian's sidebar is a DOM container
- Can update elements with `innerText` or `textContent`
- Typewriter effect via `requestAnimationFrame` with character batching
- Message queue persists across streams

---

## 4. Connection State Machine

```
    ┌─────────────┐
    │ DISCONNECTED│◄──────────────────────────┐
    └──────┬──────┘                           │
           │ connect()                        │
           ▼                                  │ reconnect()
    ┌─────────────┐                           │
    │ CONNECTING  │──────────────────────────►│
    └──────┬──────┘                           │
           │ success                          │ failure
           ▼                                  │
    ┌─────────────┐                           │
    │ CONNECTED   │──────────────────────────►│
    └──────┬──────┘                           │
           │ disconnect() / close             │
           ▼                                  │
    ┌─────────────┐                           │
    │ DISCONNECTED│◄──────────────────────────┘
```

### State → UI Indicators

| State | Sidebar Indicator | Status Bar |
|-------|-------------------|------------|
| `disconnected` | ⚪ Gray dot | "Agent: 离线" |
| `connecting` | 🟡 Yellow pulse | "Agent: 连接中..." |
| `connected` | 🟢 Green dot | "Agent: 清醒" |
| `reconnecting` | 🟠 Orange pulse | "Agent: 重新连接中..." |

---

## 5. Browser-Specific Considerations

### Electron/Chromium (Obsidian)

✅ Full WebSocket support
✅ `ws.ping()` / `ws.pong()` work
✅ `setTimeout` / `setInterval` reliable
✅ Can maintain background connections

### Future: Mobile (iOS/Android)

⚠️ WebSocket may be suspended when app backgrounded
⚠️ May need to reconnect on `visibilitychange`
⚠️ Consider reducing heartbeat frequency

---

## 6. Key Findings

1. **Heartbeat is viable**: Client-driven ping with server acknowledgment works in browsers
2. **Auto-reconnect is viable**: Exponential backoff survives network glitches
3. **Streaming is viable**: Message state machine cleanly maps to UI updates
4. **User control matters**: Must allow explicit disconnect vs auto-reconnect

---

## 7. Open Questions

- [ ] How to handle message ordering when chunks arrive out of order?
- [ ] Should we buffer messages when disconnected and replay on reconnect?
- [ ] How to handle very long thinking chains (token limit)?

---

## 8. Prototype Commands

```bash
cd /home/hedaas/桌面/Conway\'s\ Agent/node
npx ts-node prototypes/plugin_ws_client/tui.ts
```

Then interact:
- `[s]` - Start mock server
- `[c]` - Connect
- `[m Hello]` - Send message
- `[t chunk1|chunk2]` - Simulate thinking
- `[r text]` - Simulate response
- `[p]` - Print state
- `[q]` - Quit
