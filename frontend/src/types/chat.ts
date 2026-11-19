export type SourceCitation = {
  document_id: string;
  document_name: string;
  chunk_id: string;
  page_number: number | null;
  source_text: string;
  similarity_score: number;
};

export type ConversationSummary = {
  id: string;
  organization_id: string;
  title: string;
  created_at: string;
  updated_at: string;
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations: SourceCitation[];
  provider?: string | null;
  model?: string | null;
  created_at?: string;
};

export type ChatStreamEvent =
  | { type: "start"; conversation_id: string; user_message_id: string }
  | { type: "sources"; citations: SourceCitation[]; no_relevant_sources: boolean }
  | { type: "delta"; text: string }
  | { type: "done"; conversation_id: string; message_id: string; answer: string; citations: SourceCitation[]; no_relevant_sources: boolean }
  | { type: "error"; detail: string };
