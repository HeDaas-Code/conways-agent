import { describe, it, expect, vi, beforeEach } from 'vitest';
import { StreamRenderer, StreamState } from '../src/stream-renderer';
import { WSMessage } from '../src/ws-messages';

describe('StreamRenderer', () => {
  let renderer: StreamRenderer;
  let stateChanges: StreamState[];
  let thinkingStart: string | null;
  let thinkingChunks: string[];
  let thinkingDone: string | null;
  let responseChunks: string[];
  let responseDone: string | null;
  let errors: Array<{ code: string; message: string }>;

  beforeEach(() => {
    stateChanges = [];
    thinkingStart = null;
    thinkingChunks = [];
    thinkingDone = null;
    responseChunks = [];
    responseDone = null;
    errors = [];

    renderer = new StreamRenderer({
      onThinkingStart: (msgId) => { thinkingStart = msgId; },
      onThinkingChunk: (chunk) => { thinkingChunks.push(chunk); },
      onThinkingDone: (text) => { thinkingDone = text; },
      onResponseChunk: (chunk) => { responseChunks.push(chunk); },
      onResponseDone: (text) => { responseDone = text; },
      onError: (code, msg) => { errors.push({ code, message: msg }); },
      onStateChange: (state) => { stateChanges.push(state); },
    });
  });

  describe('state machine', () => {
    it('should start in idle state', () => {
      expect(renderer.getState()).toBe('idle');
    });

    it('should transition to thinking on thinking_start', () => {
      const msg: WSMessage = { type: 'thinking_start', payload: { messageId: '123' } };
      renderer.processMessage(msg);

      expect(renderer.getState()).toBe('thinking');
      expect(thinkingStart).toBe('123');
      expect(stateChanges).toContain('thinking');
    });

    it('should accumulate thinking chunks', () => {
      renderer.processMessage({ type: 'thinking_start', payload: {} });
      renderer.processMessage({ type: 'thinking', payload: { chunk: 'first' } });
      renderer.processMessage({ type: 'thinking', payload: { chunk: ' second' } });

      expect(thinkingChunks).toEqual(['first', ' second']);
      expect(renderer.getContext().thinkingBuffer).toBe('first second');
    });

    it('should transition to responding on thinking_done', () => {
      renderer.processMessage({ type: 'thinking_start', payload: {} });
      renderer.processMessage({ type: 'thinking', payload: { chunk: 'thoughts' } });
      renderer.processMessage({ type: 'thinking_done', payload: null });

      expect(renderer.getState()).toBe('responding');
      expect(thinkingDone).toBe('thoughts');
      expect(stateChanges).toContain('responding');
    });

    it('should accumulate response chunks', () => {
      renderer.processMessage({ type: 'thinking_start', payload: {} });
      renderer.processMessage({ type: 'thinking_done', payload: null });
      renderer.processMessage({ type: 'response', payload: { text: 'part1' } });
      renderer.processMessage({ type: 'response', payload: { text: 'part2' } });

      expect(responseChunks).toEqual(['part1', 'part2']);
      expect(renderer.getContext().responseBuffer).toBe('part1part2');
    });

    it('should transition to complete on response done (via complete())', () => {
      renderer.processMessage({ type: 'thinking_start', payload: {} });
      renderer.processMessage({ type: 'thinking_done', payload: null });
      renderer.processMessage({ type: 'response', payload: { text: 'response text' } });
      
      renderer.complete();

      expect(responseDone).toBe('response text');
      expect(renderer.getState()).toBe('idle');
    });
  });

  describe('error handling', () => {
    it('should handle error messages', () => {
      renderer.processMessage({ type: 'thinking_start', payload: {} });
      renderer.processMessage({ type: 'thinking', payload: { chunk: 'partial' } });
      renderer.processMessage({ type: 'error', payload: { code: 'E_TIMEOUT', message: 'Request timed out' } });

      expect(errors).toEqual([{ code: 'E_TIMEOUT', message: 'Request timed out' }]);
      expect(renderer.getState()).toBe('idle');
      expect(renderer.getContext().thinkingBuffer).toBe('');
    });
  });

  describe('isThinking / isResponding helpers', () => {
    it('should report thinking state correctly', () => {
      expect(renderer.isThinking()).toBe(false);
      
      renderer.processMessage({ type: 'thinking_start', payload: {} });
      expect(renderer.isThinking()).toBe(true);
      
      renderer.processMessage({ type: 'thinking_done', payload: null });
      expect(renderer.isThinking()).toBe(false);
    });

    it('should report responding state correctly', () => {
      expect(renderer.isResponding()).toBe(false);
      
      renderer.processMessage({ type: 'thinking_start', payload: {} });
      renderer.processMessage({ type: 'thinking_done', payload: null });
      expect(renderer.isResponding()).toBe(true);
      
      renderer.complete();
      expect(renderer.isResponding()).toBe(false);
    });
  });

  describe('full flow', () => {
    it('should handle complete stream flow', () => {
      // Start thinking
      renderer.processMessage({ type: 'thinking_start', payload: { messageId: 'msg-1' } });
      expect(renderer.getState()).toBe('thinking');
      expect(renderer.getContext().messageId).toBe('msg-1');

      // Accumulate thinking
      renderer.processMessage({ type: 'thinking', payload: { chunk: 'Let me think about this...' } });
      expect(renderer.getContext().thinkingBuffer).toBe('Let me think about this...');

      // End thinking
      renderer.processMessage({ type: 'thinking_done', payload: null });
      expect(renderer.getState()).toBe('responding');

      // Accumulate response
      renderer.processMessage({ type: 'response', payload: { text: 'Here is my ' } });
      renderer.processMessage({ type: 'response', payload: { text: 'response.' } });
      expect(renderer.getContext().responseBuffer).toBe('Here is my response.');

      // Complete
      renderer.complete();
      expect(responseDone).toBe('Here is my response.');
      expect(renderer.getState()).toBe('idle');
    });
  });
});
