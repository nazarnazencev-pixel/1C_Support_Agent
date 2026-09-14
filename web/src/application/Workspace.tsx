import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import type { Conversation, Message } from '../domain/models';
import { api } from '../infrastructure/api';
import { createIdentifier } from '../infrastructure/identifier';
import { createAnswerRenderer } from '../infrastructure/answer-renderer';
import {
  newConversation,
  readConversations,
  saveConversations,
} from '../infrastructure/conversation-storage';

function useWorkspaceState() {
  const [conversations, setConversations] = useState(readConversations);
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [partialAnswer, setPartialAnswer] = useState('');
  const [pendingAnswerId, setPendingAnswerId] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [storageError, setStorageError] = useState(false);
  const [authorization, setAuthorization] = useState('');
  const [connection, setConnection] = useState<'checking' | 'online' | 'offline'>('checking');
  const [knowledgeEditable, setKnowledgeEditable] = useState(false);
  const requestLock = useRef(false);

  useEffect(() => {
    setStorageError(!saveConversations(conversations));
  }, [conversations]);
  useEffect(() => {
    let active = true;
    const check = async () => {
      try {
        const health = await api.health();
        if (active) {
          setConnection('online');
          setKnowledgeEditable(health.knowledge_editable);
        }
      } catch {
        if (active) setConnection('offline');
      }
    };
    void check();
    const intervalId = window.setInterval(check, 60_000);
    return () => {
      active = false;
      window.clearInterval(intervalId);
    };
  }, []);

  const updateConversation = useCallback(
    (conversationId: string, update: (conversation: Conversation) => Conversation) => {
      setConversations((current) =>
        current.map((conversation) =>
          conversation.id === conversationId ? update(conversation) : conversation,
        ),
      );
    },
    [],
  );

  const send = async (content: string, conversationId?: string, file?: File): Promise<string | undefined> => {
    if (requestLock.current || !content.trim()) return;
    requestLock.current = true;
    const conversation = conversations.find((item) => item.id === conversationId) || newConversation();
    if (!conversationId || !conversations.some((item) => item.id === conversationId))
      setConversations((current) => [conversation, ...current]);
    const userMessage: Message = {
      id: createIdentifier(),
      role: 'user',
      content: content.trim(),
      createdAt: new Date().toISOString(),
      attachment: file?.name,
    };
    updateConversation(conversation.id, (current) => ({
      ...current,
      title: current.messages.length ? current.title : content.trim().slice(0, 70),
      messages: [...current.messages, userMessage],
      feedback: null,
      updatedAt: userMessage.createdAt,
    }));
    setPendingId(conversation.id);
    setPartialAnswer('');
    const answerId = createIdentifier();
    setPendingAnswerId(answerId);
    setError(null);
    void (async () => {
      let receivedText = '';
      const renderer = createAnswerRenderer(setPartialAnswer, window.matchMedia('(prefers-reduced-motion: reduce)').matches);
      const onDelta = (fragment: string) => {
        receivedText += fragment;
        renderer.append(fragment);
      };
      try {
        const response = file
          ? await api.upload(conversation.id, content, file, onDelta)
          : await api.send(conversation.id, content, onDelta);
        const answer: Message = {
          id: answerId,
          role: 'assistant',
          content: response.answer,
          createdAt: new Date().toISOString(),
        };
        updateConversation(conversation.id, (current) => ({
          ...current,
          messages: [...current.messages, answer],
          updatedAt: answer.createdAt,
        }));
        await renderer.finish(response.answer);
        setConnection('online');
      } catch (failure) {
        setError(failure instanceof Error ? failure.message : 'Не удалось отправить сообщение.');
        updateConversation(conversation.id, (current) => ({
          ...current,
          messages: [...current.messages.map((message) =>
            message.id === userMessage.id ? { ...message, failed: true } : message,
          ), ...(receivedText ? [{ id: createIdentifier(), role: 'assistant' as const, content: receivedText, createdAt: new Date().toISOString(), failed: true }] : [])],
        }));
      } finally {
        renderer.cancel();
        requestLock.current = false;
        setPendingId(null);
        setPartialAnswer('');
        setPendingAnswerId('');
      }
    })();
    return conversation.id;
  };
  const removeConversation = (conversationId: string) => {
    if (pendingId !== conversationId)
      setConversations((current) => current.filter((conversation) => conversation.id !== conversationId));
  };
  return {
    conversations,
    pendingId,
    partialAnswer,
    pendingAnswerId,
    error,
    setError,
    storageError,
    send,
    removeConversation,
    updateConversation,
    authorization,
    setAuthorization,
    connection,
    knowledgeEditable,
  };
}

const WorkspaceContext = createContext<ReturnType<typeof useWorkspaceState> | null>(null);
export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const workspace = useWorkspaceState();
  return <WorkspaceContext.Provider value={workspace}>{children}</WorkspaceContext.Provider>;
}
export function useWorkspace() {
  const workspace = useContext(WorkspaceContext);
  if (!workspace) throw new Error('WorkspaceProvider is required');
  return workspace;
}
