import { API_BASE_URL, ApiError, getErrorMessage } from "./client";
import type { ChatMessage, ChatStreamEvent, ConversationSummary, SourceCitation } from "../types/chat";

export function listConversations() {
  return jsonRequest<ConversationSummary[]>("/chat/conversations");
}

export function getConversation(id: string) {
  return jsonRequest<{ id: string; title: string; messages: ChatMessage[] }>(
    `/chat/conversations/${encodeURIComponent(id)}`,
  );
}

export async function streamChat(
  payload: { question: string; conversation_id?: string },
  onEvent: (event: ChatStreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  let response: Response;
  try {
    const token = window.sessionStorage.getItem("securedocs.accessToken");
    response = await fetch(`${API_BASE_URL}/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(payload),
      signal,
    });
  } catch {
    throw new ApiError(0, "Cannot reach the API. Please retry your question.");
  }
  if (!response.ok) {
    const body: unknown = await response.json().catch(() => undefined);
    throw new ApiError(response.status, getErrorMessage(body, "Could not answer this question."), body);
  }
  if (!response.body) throw new ApiError(0, "The answer stream was empty. Please retry.");

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });
    const blocks = buffer.split("\n\n");
    buffer = blocks.pop() ?? "";
    for (const block of blocks) parseEvent(block, onEvent);
    if (done) break;
  }
  if (buffer.trim()) parseEvent(buffer, onEvent);
}

async function jsonRequest<T>(path: string): Promise<T> {
  let response: Response;
  try {
    const token = window.sessionStorage.getItem("securedocs.accessToken");
    response = await fetch(`${API_BASE_URL}${path}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
  } catch {
    throw new ApiError(0, "Cannot reach the API. Please try again.");
  }
  const body: unknown = await response.json().catch(() => undefined);
  if (!response.ok) throw new ApiError(response.status, getErrorMessage(body, "Could not load conversations."), body);
  return body as T;
}

function parseEvent(block: string, onEvent: (event: ChatStreamEvent) => void) {
  const name = block.split("\n").find((line) => line.startsWith("event: "))?.slice(7);
  const data = block.split("\n").find((line) => line.startsWith("data: "))?.slice(6);
  if (!name || !data) return;
  const value = JSON.parse(data) as Record<string, unknown>;
  if (name === "start") onEvent({ type: "start", conversation_id: String(value.conversation_id), user_message_id: String(value.user_message_id) });
  else if (name === "sources") onEvent({ type: "sources", citations: value.citations as SourceCitation[], no_relevant_sources: Boolean(value.no_relevant_sources) });
  else if (name === "delta") onEvent({ type: "delta", text: String(value.text ?? "") });
  else if (name === "done") onEvent({ type: "done", conversation_id: String(value.conversation_id), message_id: String(value.message_id), answer: String(value.answer ?? ""), citations: value.citations as SourceCitation[], no_relevant_sources: Boolean(value.no_relevant_sources) });
  else if (name === "error") onEvent({ type: "error", detail: String(value.detail ?? "Generation failed.") });
}
