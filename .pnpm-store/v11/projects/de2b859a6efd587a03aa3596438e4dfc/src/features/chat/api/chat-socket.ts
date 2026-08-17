import { API_BASE } from "@/config/env";

export type SocketEvent = Record<string, unknown>;

export function socketUrl(): string {
  const url = new URL(API_BASE);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  url.pathname = "/api/v1/ws";
  return url.toString();
}

export function newClientMessageId(): string {
  return globalThis.crypto?.randomUUID?.() || `web-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}
