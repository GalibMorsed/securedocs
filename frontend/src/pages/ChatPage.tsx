import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { getConversation, listConversations, streamChat } from "../api/chat";
import type { ChatMessage, ChatStreamEvent, ConversationSummary, SourceCitation } from "../types/chat";

const pendingMessageId = "securedocs-pending-assistant";

export function ChatPage() {
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [question, setQuestion] = useState("");
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastQuestion, setLastQuestion] = useState("");
  const scrollTarget = useRef<HTMLDivElement>(null);

  const refreshConversations = useCallback(async () => {
    try { setConversations(await listConversations()); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Could not load conversation history."); }
  }, []);

  useEffect(() => {
    void refreshConversations().finally(() => setLoadingHistory(false));
  }, [refreshConversations]);

  useEffect(() => { scrollTarget.current?.scrollIntoView?.({ behavior: "smooth", block: "end" }); }, [messages]);

  async function selectConversation(id: string) {
    if (sending) return;
    setError(null); setLoadingHistory(true);
    try {
      const selected = await getConversation(id);
      setConversationId(selected.id); setMessages(selected.messages);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not load this conversation."); }
    finally { setLoadingHistory(false); }
  }

  function startNewConversation() {
    if (sending) return;
    setConversationId(null); setMessages([]); setQuestion(""); setError(null);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await send(question.trim());
  }

  async function send(text: string) {
    if (sending || text.length < 2) return;
    setError(null); setQuestion(""); setSending(true); setLastQuestion(text);
    let activeConversation = conversationId;
    let citations: SourceCitation[] = [];
    let provisionalAdded = false;
    try {
      await streamChat({ question: text, ...(activeConversation ? { conversation_id: activeConversation } : {}) }, (event: ChatStreamEvent) => {
        if (event.type === "start") {
          activeConversation = event.conversation_id;
          setConversationId(event.conversation_id);
          setMessages((current) => [...current,
            { id: event.user_message_id, role: "user", content: text, citations: [] },
            { id: pendingMessageId, role: "assistant", content: "", citations: [] },
          ]);
          provisionalAdded = true;
        } else if (event.type === "sources") {
          citations = event.citations;
          setMessages((current) => current.map((message) => message.id === pendingMessageId ? { ...message, citations } : message));
        } else if (event.type === "delta") {
          setMessages((current) => current.map((message) => message.id === pendingMessageId ? { ...message, content: message.content + event.text } : message));
        } else if (event.type === "done") {
          setConversationId(event.conversation_id);
          setMessages((current) => current.map((message) => message.id === pendingMessageId ? { ...message, id: event.message_id, content: event.answer, citations: event.citations } : message));
          void refreshConversations();
        } else if (event.type === "error") {
          setError(event.detail);
        }
      });
      if (!provisionalAdded) setError("The answer stream ended before it started. Please retry.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not answer your question. Please retry.");
      if (provisionalAdded && citations.length) {
        setMessages((current) => current.map((message) => message.id === pendingMessageId ? { ...message, citations } : message));
      }
    } finally { setSending(false); }
  }

  return <main className="mx-auto grid max-w-7xl gap-6 px-5 py-8 sm:px-8 lg:grid-cols-[280px_minmax(0,1fr)]">
    <aside className="rounded-xl border border-line bg-white p-4 shadow-sm" aria-label="Conversation history">
      <div className="flex items-center justify-between gap-3"><h2 className="font-semibold">Conversations</h2><button type="button" onClick={startNewConversation} disabled={sending} className="rounded-md bg-accent px-3 py-2 text-sm font-semibold text-white disabled:opacity-50">New chat</button></div>
      <ul className="mt-4 max-h-[68vh] space-y-1 overflow-y-auto">
        {conversations.map((conversation) => <li key={conversation.id}><button type="button" onClick={() => void selectConversation(conversation.id)} className={`w-full rounded-lg px-3 py-2 text-left text-sm hover:bg-slate-50 ${conversationId === conversation.id ? "bg-blue-50 text-accent" : "text-ink"}`}><span className="block truncate font-medium">{conversation.title}</span><span className="mt-1 block text-xs text-muted">{formatDate(conversation.updated_at)}</span></button></li>)}
      </ul>
      {loadingHistory && <p role="status" className="mt-3 text-xs text-muted">Loading conversations…</p>}
      {!loadingHistory && conversations.length === 0 && <p className="mt-4 text-sm text-muted">Your saved conversations will appear here.</p>}
    </aside>

    <section className="flex min-h-[72vh] flex-col rounded-xl border border-line bg-white shadow-sm" aria-label="SecureDocs chat">
      <header className="border-b border-line p-5"><p className="text-sm font-semibold text-accent">DOCUMENT ASSISTANT</p><h1 className="mt-1 text-2xl font-semibold">Grounded answers</h1><p className="mt-1 text-sm text-muted">Answers use documents your organization is authorized to access.</p></header>
      <div className="flex-1 space-y-5 overflow-y-auto p-5 sm:p-7" aria-live="polite">
        {messages.length === 0 && <div className="mx-auto mt-12 max-w-xl text-center"><h2 className="text-lg font-semibold">Ask about your documents</h2><p className="mt-2 text-sm leading-6 text-muted">The assistant searches processed documents and shows the exact passages used. For scanned files, wait for OCR and processing to finish.</p><Link className="mt-4 inline-block font-semibold text-accent hover:underline" to="/search">Open passage search</Link></div>}
        {messages.map((message) => <article key={message.id} className={`max-w-3xl ${message.role === "user" ? "ml-auto" : "mr-auto"}`}>
          <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted">{message.role === "user" ? "You" : "SecureDocs"}</p>
          <div className={`rounded-xl px-4 py-3 text-sm leading-6 ${message.role === "user" ? "bg-blue-50 text-ink dark:bg-slate-800" : "bg-slate-50 text-ink dark:bg-slate-900"}`}>
            {message.content || (sending ? <span role="status">Searching sources and drafting an answer…</span> : "")}
            {message.role === "assistant" && message.citations.length > 0 && <div className="mt-4 border-t border-line pt-3"><p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">Sources verified by SecureDocs</p><ul className="space-y-2">{message.citations.map((source) => <li key={source.chunk_id} className="rounded-lg border border-line bg-white p-3 dark:bg-slate-800"><Link to={`/documents#document-${source.document_id}`} className="font-semibold text-accent hover:underline">{source.document_name}{source.page_number ? ` · Page ${source.page_number}` : ""}</Link><p className="mt-1 whitespace-pre-wrap text-xs leading-5 text-muted">{source.source_text}</p><p className="mt-1 text-[11px] text-muted">Similarity {Math.round(source.similarity_score * 100)}%</p></li>)}</ul></div>}
          </div>
          {message.role === "assistant" && message.id !== pendingMessageId && <button type="button" onClick={() => void navigator.clipboard?.writeText(message.content)} className="mt-2 text-xs font-medium text-accent hover:underline">Copy answer</button>}
        </article>)}
        <div ref={scrollTarget} />
      </div>
      {error && <div role="alert" className="mx-5 mb-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-fail sm:mx-7">{error}{lastQuestion && <button type="button" onClick={() => void send(lastQuestion)} disabled={sending} className="ml-3 font-semibold underline">Retry</button>}</div>}
      <form onSubmit={(event) => void submit(event)} className="border-t border-line p-4 sm:p-5"><label className="sr-only" htmlFor="chat-question">Ask a question about your documents</label><div className="flex items-end gap-3"><textarea id="chat-question" value={question} onChange={(event) => setQuestion(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); event.currentTarget.form?.requestSubmit(); } }} maxLength={4000} rows={2} placeholder="Ask a question about your organization’s files…" disabled={sending} className="min-h-12 flex-1 resize-y rounded-lg border border-line px-3.5 py-3 text-sm outline-none focus:border-accent focus:ring-4 focus:ring-blue-100"/><button type="submit" disabled={sending || question.trim().length < 2} className="rounded-lg bg-accent px-5 py-3 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60">{sending ? "Answering…" : "Send"}</button></div><p className="mt-2 text-xs text-muted">Answers may be incomplete; verify important details in the cited source passages.</p></form>
    </section>
  </main>;
}

function formatDate(value: string) { return new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(new Date(value)); }
