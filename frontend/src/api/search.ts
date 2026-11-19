import { apiRequest } from "./client";
import type { SearchResponse } from "../types/search";

export function searchDocuments(query: string, topK = 8) {
  return apiRequest<SearchResponse>("/search", {
    method: "POST",
    body: JSON.stringify({ query, top_k: topK }),
  });
}
