import { API_BASE_URL } from './api';

export type ChatReference = {
  source_id: string;
  chunk_id: string | null;
  document_id: string | null;
  title: string;
  source_url: string;
  page_numbers: number[];
  source_type: string;
};

export type TranscriptTurn = {
  turn_id: string;
  question: string;
  status: string;
  answer: string;
  references: ChatReference[];
  action_required: boolean;
  action_status: string;
};

export type ChatStreamEvent = {
  event: string;
  data: Record<string, unknown>;
};

/** Incrementally decode SSE records across arbitrary byte boundaries. */
export class SseParser {
  private readonly decoder = new TextDecoder();
  private buffer = '';

  push(chunk: Uint8Array): ChatStreamEvent[] {
    this.buffer += this.decoder.decode(chunk, { stream: true });
    return this.drain();
  }

  finish(): ChatStreamEvent[] {
    this.buffer += this.decoder.decode();
    const events = this.drain();
    if (this.buffer.trim()) {
      throw new Error('The server returned an incomplete SSE event.');
    }
    return events;
  }

  private drain(): ChatStreamEvent[] {
    // Keep a trailing carriage return buffered so a split CRLF normalizes later.
    this.buffer = this.buffer.replace(/\r\n/g, '\n');
    const records = this.buffer.split('\n\n');
    this.buffer = records.pop() ?? '';
    return records.flatMap((record) => {
      if (!record.trim()) return [];
      let eventName = 'message';
      const dataLines: string[] = [];
      for (const line of record.split('\n')) {
        if (line.startsWith('event:')) eventName = line.slice(6).trim();
        if (line.startsWith('data:')) dataLines.push(line.slice(5).trimStart());
      }
      if (dataLines.length === 0) return [];
      try {
        return [{ event: eventName, data: JSON.parse(dataLines.join('\n')) }];
      } catch {
        throw new Error('The server returned invalid JSON in an SSE event.');
      }
    });
  }
}

async function apiError(response: Response): Promise<Error> {
  try {
    const payload = await response.json();
    const detail = typeof payload.detail === 'string' ? payload.detail : null;
    return new Error(detail ?? 'The assistant service is unavailable.');
  } catch {
    return new Error('The assistant service is unavailable.');
  }
}

export async function streamChat(
  question: string,
  onEvent: (event: ChatStreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/chat`, {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRF-Protection': '1',
    },
    body: JSON.stringify({ question }),
    signal,
  });
  if (!response.ok) throw await apiError(response);
  if (!response.body) throw new Error('The server did not provide a response stream.');

  const reader = response.body.getReader();
  const parser = new SseParser();
  let completed = false;
  let failed = false;
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    for (const event of parser.push(value)) {
      completed ||= event.event === 'complete';
      failed ||= event.event === 'error';
      onEvent(event);
    }
  }
  for (const event of parser.finish()) {
    completed ||= event.event === 'complete';
    failed ||= event.event === 'error';
    onEvent(event);
  }
  if (!completed && !failed) {
    throw new Error('The response stream ended before completion.');
  }
}

export async function getChatHistory(signal?: AbortSignal): Promise<TranscriptTurn[]> {
  const response = await fetch(`${API_BASE_URL}/chat/history`, {
    credentials: 'include',
    cache: 'no-store',
    signal,
  });
  if (!response.ok) throw await apiError(response);
  const payload = await response.json();
  return payload.turns as TranscriptTurn[];
}

export async function startNewConversation(): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/chat/new`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'X-CSRF-Protection': '1' },
  });
  if (!response.ok) throw await apiError(response);
}
