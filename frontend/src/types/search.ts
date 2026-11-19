export type SearchResult = {
  document_id: string;
  document_name: string;
  chunk_id: string;
  content: string;
  page_number: number | null;
  similarity_score: number;
};

export type SearchResponse = { results: SearchResult[] };
