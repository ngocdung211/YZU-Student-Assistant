'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import {
  ChatReference,
  getChatHistory,
  startNewConversation,
  streamChat,
} from '../lib/chat';

export type ChatMessage = {
  id: string;
  role: 'student' | 'assistant';
  content: string;
  references: ChatReference[];
  state: 'complete' | 'loading' | 'error';
};

function restoredMessages(turns: Awaited<ReturnType<typeof getChatHistory>>): ChatMessage[] {
  return turns.flatMap((turn) => [
    {
      id: `${turn.turn_id}-question`,
      role: 'student' as const,
      content: turn.question,
      references: [],
      state: 'complete' as const,
    },
    {
      id: `${turn.turn_id}-answer`,
      role: 'assistant' as const,
      content: turn.answer,
      references: turn.references,
      state: 'complete' as const,
    },
  ]);
}

export function useChatSession() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoadingHistory, setIsLoadingHistory] = useState(true);
  const [isSending, setIsSending] = useState(false);
  const [isResetting, setIsResetting] = useState(false);
  const [notice, setNotice] = useState('');
  const activeRequest = useRef<AbortController | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    getChatHistory(controller.signal)
      .then((turns) => setMessages(restoredMessages(turns)))
      .catch((error: unknown) => {
        if ((error as Error).name !== 'AbortError') {
          setNotice('Previous messages could not be loaded. You can still try a new question.');
        }
      })
      .finally(() => setIsLoadingHistory(false));
    return () => controller.abort();
  }, []);

  const send = useCallback(async (rawQuestion: string) => {
    const question = rawQuestion.trim();
    if (!question || isSending || isResetting) return false;

    const requestId = crypto.randomUUID();
    const controller = new AbortController();
    activeRequest.current = controller;
    setNotice('');
    setIsSending(true);
    setMessages((current) => [...current,
      { id: `${requestId}-question`, role: 'student', content: question,
        references: [], state: 'complete' },
      { id: `${requestId}-answer`, role: 'assistant', content: '',
        references: [], state: 'loading' },
    ]);

    const updateAnswer = (change: Partial<ChatMessage>) => {
      setMessages((current) => current.map((message) =>
        message.id === `${requestId}-answer` ? { ...message, ...change } : message));
    };

    try {
      await streamChat(question, ({ event, data }) => {
        if (event === 'answer') {
          updateAnswer({ content: String(data.answer ?? '') });
        } else if (event === 'references') {
          updateAnswer({ references: (data.references ?? []) as ChatReference[] });
        } else if (event === 'complete') {
          updateAnswer({ state: 'complete' });
        } else if (event === 'error') {
          updateAnswer({
            content: String(data.message ?? 'The assistant could not finish this response.'),
            state: 'error',
          });
        }
      }, controller.signal);
      return true;
    } catch (error) {
      const interrupted = (error as Error).name === 'AbortError';
      updateAnswer({
        content: interrupted
          ? 'This response was interrupted.'
          : (error as Error).message || 'The assistant could not finish this response.',
        state: 'error',
      });
      return false;
    } finally {
      if (activeRequest.current === controller) activeRequest.current = null;
      setIsSending(false);
    }
  }, [isResetting, isSending]);

  const reset = useCallback(async () => {
    if (isResetting) return;
    activeRequest.current?.abort();
    setNotice('');
    setIsResetting(true);
    try {
      await startNewConversation();
      setMessages([]);
    } catch (error) {
      setNotice((error as Error).message || 'The conversation could not be reset.');
    } finally {
      setIsResetting(false);
    }
  }, [isResetting]);

  return {
    messages,
    isLoadingHistory,
    isSending,
    isResetting,
    notice,
    send,
    reset,
  };
}
