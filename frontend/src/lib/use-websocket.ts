/** Realtime chat socket.
 *
 * Protocol as implemented by the backend (`src/api/websocket.py`): one socket
 * per user, not per conversation, with the token sent as the first frame rather
 * than in the URL — query strings end up in access logs and Referer headers.
 *
 *   -> {"type":"auth","token":"..."}            within 10s or the server closes 4401
 *   <- {"type":"auth_ok","user_id":"..."}
 *   -> {"type":"send_message","client_message_id","conversation_id","text"}
 *   <- {"type":"message_created", client_message_id, message}   to the sender
 *   <- {"type":"message_received", message}                     to other members
 *   <- {"type":"translation_completed", ...}                    to readers of that language
 *   <- {"type":"error", code, message}
 */

"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { getToken } from "./auth";
import { API_BASE } from "./constants";

const AUTH_TIMEOUT_MS = 10_000;
const BACKOFF_STEPS_MS = [1_000, 2_000, 4_000, 8_000, 16_000, 30_000];

/** Server errors that mean retrying will not help. */
const FATAL_ERROR_CODES = new Set([
  "authentication_failed",
  "authentication_required",
  "authentication_timeout",
]);

export interface RealtimeMessage {
  id: string;
  conversation_id: string;
  sender_id: string;
  original_text: string;
  created_at: string;
}

export interface TranslationCompleted {
  type: "translation_completed";
  message_id: string;
  conversation_id: string;
  translation_id: string;
  source_language: string;
  target_language: string;
  translated_text: string;
  model: string;
  latency_ms: number;
  is_fallback: boolean;
}

export interface ChatSocketHandlers {
  /** The sender's own message came back with its server id. */
  onMessageCreated?: (clientMessageId: string, message: RealtimeMessage) => void;
  /** Somebody else sent a message. */
  onMessageReceived?: (message: RealtimeMessage) => void;
  /** A translation finished for a language this account reads. */
  onTranslationCompleted?: (event: TranslationCompleted) => void;
  /** A non-fatal application error. */
  onError?: (code: string, message: string) => void;
  /** The session is unusable; the caller should send the user back to login. */
  onAuthFailure?: () => void;
}

export interface ChatSocket {
  connected: boolean;
  /** Send a message. Returns false when the socket is not ready. */
  sendMessage: (input: {
    clientMessageId: string;
    conversationId: string;
    text: string;
  }) => boolean;
}

function socketUrl(): string {
  return `${API_BASE.replace(/^http/, "ws")}/api/v1/ws`;
}

/**
 * @param handlers Callbacks for each server event.
 * @param authToken Token to authenticate with. Defaults to the stored session;
 *   passing one explicitly is what lets two accounts share a tab in the demo.
 */
export function useWebSocket(handlers: ChatSocketHandlers, authToken?: string): ChatSocket {
  const [connected, setConnected] = useState(false);

  const socketRef = useRef<WebSocket | null>(null);
  const reconnectRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const authTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const attemptRef = useRef(0);
  const closedByUsRef = useRef(false);

  // Handlers change on every render of the caller; a ref keeps the socket from
  // being torn down and rebuilt each time.
  const handlersRef = useRef(handlers);
  useEffect(() => {
    handlersRef.current = handlers;
  });

  // The reconnect timer has to call `connect` from inside `connect` itself.
  // Going through a ref avoids the circular dependency.
  const connectRef = useRef<() => void>(() => {});

  const connect = useCallback(() => {
    const token = authToken ?? getToken();
    if (!token) {
      handlersRef.current.onAuthFailure?.();
      return;
    }

    const socket = new WebSocket(socketUrl());
    socketRef.current = socket;
    // Local to this socket rather than read from state, which would be stale
    // by the time the timer fires.
    let authenticated = false;

    socket.onopen = () => {
      socket.send(JSON.stringify({ type: "auth", token }));
      // The server closes the socket if auth does not complete in time; give up
      // on our side too rather than sitting on a half-open connection.
      authTimerRef.current = setTimeout(() => {
        if (!authenticated) socket.close();
      }, AUTH_TIMEOUT_MS);
    };

    socket.onmessage = (raw) => {
      let event: Record<string, unknown>;
      try {
        event = JSON.parse(raw.data as string);
      } catch {
        return;
      }

      const callbacks = handlersRef.current;
      switch (event.type) {
        case "auth_ok":
          if (authTimerRef.current) clearTimeout(authTimerRef.current);
          authenticated = true;
          attemptRef.current = 0;
          setConnected(true);
          break;
        case "message_created":
          callbacks.onMessageCreated?.(
            event.client_message_id as string,
            event.message as RealtimeMessage,
          );
          break;
        case "message_received":
          callbacks.onMessageReceived?.(event.message as RealtimeMessage);
          break;
        case "translation_completed":
          callbacks.onTranslationCompleted?.(event as unknown as TranslationCompleted);
          break;
        case "error": {
          const code = event.code as string;
          if (FATAL_ERROR_CODES.has(code)) {
            // Reconnecting with the same rejected token would loop forever.
            closedByUsRef.current = true;
            callbacks.onAuthFailure?.();
            socket.close();
            return;
          }
          callbacks.onError?.(code, event.message as string);
          break;
        }
      }
    };

    socket.onclose = () => {
      setConnected(false);
      if (closedByUsRef.current) return;

      const delay = BACKOFF_STEPS_MS[Math.min(attemptRef.current, BACKOFF_STEPS_MS.length - 1)];
      attemptRef.current += 1;
      reconnectRef.current = setTimeout(() => connectRef.current(), delay);
    };
  }, [authToken]);

  useEffect(() => {
    connectRef.current = connect;
  }, [connect]);

  useEffect(() => {
    closedByUsRef.current = false;
    connect();

    return () => {
      // React 19 StrictMode mounts effects twice in development. Without
      // closing here, the demo would run two sockets and show every message
      // twice.
      closedByUsRef.current = true;
      if (reconnectRef.current) clearTimeout(reconnectRef.current);
      if (authTimerRef.current) clearTimeout(authTimerRef.current);
      socketRef.current?.close();
      socketRef.current = null;
    };
    // connect is intentionally not a dependency: re-running it would reconnect
    // on every state change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const sendMessage: ChatSocket["sendMessage"] = useCallback((input) => {
    const socket = socketRef.current;
    if (!socket || socket.readyState !== WebSocket.OPEN) return false;

    socket.send(
      JSON.stringify({
        type: "send_message",
        client_message_id: input.clientMessageId,
        conversation_id: input.conversationId,
        text: input.text,
      }),
    );
    return true;
  }, []);

  return { connected, sendMessage };
}
