import { describe, expect, it } from 'vitest';
import { SseParser } from '../lib/chat';

const encoder = new TextEncoder();

describe('SseParser', () => {
  it('buffers event and UTF-8 boundaries split across network chunks', () => {
    const parser = new SseParser();
    const bytes = encoder.encode(
      'event: answer\r\ndata: {"answer":"元智 University"}\r\n\r\n' +
      'event: complete\ndata: {"status":"complete"}\n\n',
    );
    const splitInsideCharacter = bytes.indexOf(0xe5) + 1;
    const first = parser.push(bytes.slice(0, 15));
    const second = parser.push(bytes.slice(15, splitInsideCharacter));
    const third = parser.push(bytes.slice(splitInsideCharacter));

    expect(first).toEqual([]);
    expect(second).toEqual([]);
    expect(third).toEqual([
      { event: 'answer', data: { answer: '元智 University' } },
      { event: 'complete', data: { status: 'complete' } },
    ]);
    expect(parser.finish()).toEqual([]);
  });

  it('reports malformed JSON as a stream error', () => {
    const parser = new SseParser();
    expect(() => parser.push(encoder.encode(
      'event: answer\ndata: not-json\n\n',
    ))).toThrow('invalid JSON');
  });

  it('does not dispatch an interrupted event without its delimiter', () => {
    const parser = new SseParser();
    expect(parser.push(encoder.encode(
      'event: answer\ndata: {"answer":"unfinished"}',
    ))).toEqual([]);
    expect(() => parser.finish()).toThrow('incomplete SSE event');
  });
});
