import type { DocumentPayload, DocumentRecord } from "../types/documents";
import { apiRequest } from "./client";

export function listDocuments(options: { offset?: number; limit?: number } = {}) {
  const params = new URLSearchParams();
  if (options.offset !== undefined) params.set("offset", String(options.offset));
  if (options.limit !== undefined) params.set("limit", String(options.limit));
  const query = params.size > 0 ? `?${params.toString()}` : "";
  return apiRequest<DocumentRecord[]>(`/documents${query}`);
}

export function createDocument(payload: DocumentPayload) {
  return apiRequest<DocumentRecord>("/documents", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateDocument(id: string, payload: Partial<DocumentPayload>) {
  return apiRequest<DocumentRecord>(`/documents/${encodeURIComponent(id)}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function deleteDocument(id: string) {
  return apiRequest<void>(`/documents/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
}
