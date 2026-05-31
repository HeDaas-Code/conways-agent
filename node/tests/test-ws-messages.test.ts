import { describe, it, expect } from 'vitest';
import { parse, parseFromString } from '../src/ws-messages';

describe('ws-messages', () => {
  describe('parse', () => {
    it('should parse valid JSON string as WSMessage', () => {
      const raw = '{"type":"process","payload":{"text":"hello"}}';
      const result = parse(raw);
      
      expect(result).toBeDefined();
      expect(result?.type).toBe('process');
      expect(result?.payload).toEqual({ text: 'hello' });
    });

    it('should parse message with id and timestamp', () => {
      const raw = '{"type":"activate","payload":null,"id":"123","timestamp":1234567890}';
      const result = parse(raw);
      
      expect(result?.id).toBe('123');
      expect(result?.timestamp).toBe(1234567890);
    });

    it('should return null for invalid JSON', () => {
      const raw = 'not valid json';
      expect(() => parse(raw)).toThrow('Invalid message format');
    });

    it('should return null for non-object JSON', () => {
      const raw = '"just a string"';
      expect(() => parse(raw)).toThrow('Invalid message format');
    });

    it('should return null for array JSON', () => {
      const raw = '["array", "not", "object"]';
      expect(() => parse(raw)).toThrow('Invalid message format');
    });

    it('should return null for missing type field', () => {
      const raw = '{"payload":"no type"}';
      expect(() => parse(raw)).toThrow('Invalid message format');
    });
  });

  describe('parseFromString (alias)', () => {
    it('should work as alias for parse with string input', () => {
      const raw = '{"type":"heartbeat","payload":{}}';
      const result = parseFromString(raw);
      
      expect(result?.type).toBe('heartbeat');
    });
  });
});

describe('WSMessage type validation', () => {
  it('should validate activate message', () => {
    const raw = '{"type":"activate","payload":null}';
    const result = parse(raw);
    expect(result?.type).toBe('activate');
  });

  it('should validate deactivate message', () => {
    const raw = '{"type":"deactivate","payload":null}';
    const result = parse(raw);
    expect(result?.type).toBe('deactivate');
  });

  it('should validate heartbeat message', () => {
    const raw = '{"type":"heartbeat","payload":{"ts":1234567890}}';
    const result = parse(raw);
    expect(result?.type).toBe('heartbeat');
  });

  it('should validate heartbeat_ack message', () => {
    const raw = '{"type":"heartbeat_ack","payload":null}';
    const result = parse(raw);
    expect(result?.type).toBe('heartbeat_ack');
  });

  it('should validate process message', () => {
    const raw = '{"type":"process","payload":{"text":"hello world"}}';
    const result = parse(raw);
    expect(result?.type).toBe('process');
  });

  it('should validate thinking_start message', () => {
    const raw = '{"type":"thinking_start","payload":{"messageId":"msg-123"}}';
    const result = parse(raw);
    expect(result?.type).toBe('thinking_start');
  });

  it('should validate thinking message', () => {
    const raw = '{"type":"thinking","payload":{"chunk":"analyzing..."}}';
    const result = parse(raw);
    expect(result?.type).toBe('thinking');
  });

  it('should validate thinking_done message', () => {
    const raw = '{"type":"thinking_done","payload":null}';
    const result = parse(raw);
    expect(result?.type).toBe('thinking_done');
  });

  it('should validate response message', () => {
    const raw = '{"type":"response","payload":{"text":"final response"}}';
    const result = parse(raw);
    expect(result?.type).toBe('response');
  });

  it('should validate error message', () => {
    const raw = '{"type":"error","payload":{"code":"E_TIMEOUT","message":"Request timed out"}}';
    const result = parse(raw);
    expect(result?.type).toBe('error');
  });
});
