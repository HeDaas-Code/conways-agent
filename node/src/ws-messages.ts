/**
 * WebSocket Message Types for Obsidian Plugin
 * 
 * Defines all message types and parsing functions for the WS protocol.
 */

// ─── Message Types ─────────────────────────────────────────────────────────

export type WSMessageType = 
  | 'activate'          // Plugin connection established
  | 'deactivate'       // Plugin disconnecting
  | 'heartbeat'        // Client heartbeat ping
  | 'heartbeat_ack'    // Server heartbeat response
  | 'pong'             // WebSocket pong response
  | 'process'          // User message (plugin → backend)
  | 'thinking_start'   // Thinking phase begins
  | 'thinking'         // Thinking chunk (streaming)
  | 'thinking_done'    // Thinking phase ends
  | 'response'         // Response chunk
  | 'response_end'     // Response complete
  | 'error';           // Error occurred

export interface WSMessage {
  type: WSMessageType;
  payload: unknown;
  id?: string;
  timestamp?: number;
}

// ─── Parsed Payload Types ──────────────────────────────────────────────────

export interface ProcessPayload {
  text: string;
}

export interface ThinkingStartPayload {
  messageId?: string;
}

export interface ThinkingChunkPayload {
  chunk: string;
  index?: number;
}

export interface ResponsePayload {
  text: string;
  messageId?: string;
}

export interface ErrorPayload {
  code: string;
  message: string;
}

export interface HeartbeatPayload {
  ts?: number;
}

// ─── Parser Functions ───────────────────────────────────────────────────────

/**
 * Parse raw WebSocket message into structured WSMessage format.
 * 
 * @throws Error if the message format is invalid
 */
export function parse(raw: unknown): WSMessage {
  if (typeof raw === 'string') {
    return parseFromString(raw);
  }
  
  if (Buffer.isBuffer(raw)) {
    return parseFromString(raw.toString());
  }

  if (raw instanceof Uint8Array) {
    return parseFromString(Buffer.from(raw).toString());
  }

  throw new Error('Invalid message format: expected string or buffer');
}

/**
 * Parse a JSON string into a WSMessage.
 * 
 * @throws Error if the JSON is invalid or missing required fields
 */
export function parseFromString(raw: string): WSMessage {
  let parsed: unknown;
  
  try {
    parsed = JSON.parse(raw);
  } catch {
    throw new Error('Invalid message format: invalid JSON');
  }

  if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
    throw new Error('Invalid message format: expected object');
  }

  const obj = parsed as Record<string, unknown>;

  if (typeof obj.type !== 'string') {
    throw new Error('Invalid message format: missing or invalid type field');
  }

  return {
    type: obj.type as WSMessageType,
    payload: obj.payload ?? null,
    id: typeof obj.id === 'string' ? obj.id : undefined,
    timestamp: typeof obj.timestamp === 'number' ? obj.timestamp : undefined,
  };
}

/**
 * Check if a WSMessage is a specific type.
 */
export function isType(msg: WSMessage, type: WSMessageType): boolean {
  return msg.type === type;
}

/**
 * Type guard for process messages.
 */
export function isProcessPayload(payload: unknown): payload is ProcessPayload {
  return typeof payload === 'object' && payload !== null && 'text' in payload;
}

/**
 * Type guard for thinking chunk payloads.
 */
export function isThinkingChunkPayload(payload: unknown): payload is ThinkingChunkPayload {
  return typeof payload === 'object' && payload !== null && 'chunk' in payload;
}

/**
 * Type guard for response payloads.
 */
export function isResponsePayload(payload: unknown): payload is ResponsePayload {
  return typeof payload === 'object' && payload !== null && 'text' in payload;
}

/**
 * Type guard for error payloads.
 */
export function isErrorPayload(payload: unknown): payload is ErrorPayload {
  return typeof payload === 'object' && payload !== null && 'code' in payload && 'message' in payload;
}
