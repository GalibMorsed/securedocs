import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { searchDocuments } from "../api/search";
import type { SearchResult } from "../types/search";

export function SearchPage() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [searched, setSearched] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function runSearch() {
    if (loading || query.trim().length < 2) return;
    setLoading(true); setError(null); setSearched(true);
    try { setResults((await searchDocuments(query.trim())).results); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Search failed. Please try again."); setResults([]); }
    finally { setLoading(false); }
  }
  function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); void runSearch(); }

  return <main className="mx-auto max-w-5xl px-5 py-10 sm:px-8 sm:py-14">
    <p className="text-sm font-semibold text-accent">KNOWLEDGE BASE</p>
    <h1 className="mt-2 text-3xl font-semibold tracking-tight">Semantic search</h1>
    <p className="mt-2 text-muted">Find relevant passages across your organization’s processed documents.</p>
    <form onSubmit={submit} className="mt-7 flex flex-col gap-3 rounded-xl border border-line bg-white p-4 shadow-sm sm:flex-row">
      <label className="sr-only" htmlFor="semantic-query">Search documents</label>
      <input id="semantic-query" value={query} onChange={(event) => setQuery(event.target.value)} minLength={2} maxLength={8000} placeholder="Ask a question or describe what you’re looking for…" className="min-w-0 flex-1 rounded-lg border border-line px-4 py-3 outline-none focus:border-accent focus:ring-4 focus:ring-blue-100" />
      <button disabled={loading || query.trim().length < 2} className="rounded-lg bg-accent px-6 py-3 font-semibold text-white disabled:opacity-60">{loading ? "Searching…" : "Search"}</button>
    </form>
    {loading && <p role="status" className="mt-6 text-sm text-muted">Searching your authorized documents…</p>}
    {error && <div role="alert" className="mt-6 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-fail"><p>{error}</p><button type="button" onClick={() => void runSearch()} className="mt-2 font-semibold underline">Try again</button></div>}
    {!loading && searched && !error && results.length === 0 && <div className="mt-7 rounded-xl border border-dashed border-slate-300 bg-white p-10 text-center"><h2 className="font-semibold">No matching passages</h2><p className="mt-2 text-sm text-muted">Try a different phrase, or confirm that document processing is complete.</p><Link to="/documents" className="mt-4 inline-block font-semibold text-accent">View documents</Link></div>}
    {results.length > 0 && <section className="mt-7" aria-label="Search results"><p className="mb-3 text-sm text-muted">{results.length} relevant {results.length === 1 ? "passage" : "passages"}</p><ul className="space-y-3">{results.map((result) => <li key={result.chunk_id} className="rounded-xl border border-line bg-white p-5 shadow-sm"><div className="flex flex-wrap items-baseline justify-between gap-2"><Link to={`/documents#document-${result.document_id}`} className="font-semibold text-accent hover:underline">{result.document_name}</Link><span className="text-xs text-muted">{result.page_number ? `Page ${result.page_number} · ` : ""}{Math.round(result.similarity_score * 100)}% match</span></div><p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-ink">{result.content}</p></li>)}</ul></section>}
  </main>;
}
