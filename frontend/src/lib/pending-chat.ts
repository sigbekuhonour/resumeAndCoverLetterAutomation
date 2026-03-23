"use client";

const PENDING_CHAT_PREFIX = "pending-chat:";

function keyForConversation(conversationId: string) {
  return `${PENDING_CHAT_PREFIX}${conversationId}`;
}

export function storePendingChatMessage(
  conversationId: string,
  content: string
) {
  if (typeof window === "undefined") return;
  window.sessionStorage.setItem(keyForConversation(conversationId), content);
}

export function readPendingChatMessage(conversationId: string) {
  if (typeof window === "undefined") return null;
  return window.sessionStorage.getItem(keyForConversation(conversationId));
}

export function clearPendingChatMessage(conversationId: string) {
  if (typeof window === "undefined") return;
  window.sessionStorage.removeItem(keyForConversation(conversationId));
}
