import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { ApiError } from "../api/client";
import { createDocument, deleteDocument, listDocuments } from "../api/documents";
import type { DocumentPayload, DocumentRecord, DocumentStatus } from "../types/documents";

const statusStyles: Record<DocumentStatus, string> = {
  uploaded: "bg-blue-50 text-blue-700",
  processing: "bg-amber-50 text-amber-700",
  ready: "bg-emerald-50 text-emerald-700",
  failed: "bg-red-50 text-red-700",
};

export function DocumentsPage() {
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [mimeType, setMimeType] = useState("");
  const [fileSize, setFileSize] = useState("");

  const refresh = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      setDocuments(await listDocuments());
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : "Could not load documents.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setActionError(null);
    setSaving(true);

    const payload: DocumentPayload = {
      name: name.trim(),
      description: description.trim() || null,
      mime_type: mimeType.trim() || null,
      file_size: fileSize === "" ? null : Number(fileSize),
    };

    try {
      const created = await createDocument(payload);
      setDocuments((current) => [created, ...current]);
      setFormOpen(false);
      setName("");
      setDescription("");
      setMimeType("");
      setFileSize("");
    } catch (error) {
      setActionError(error instanceof ApiError ? error.message : "Could not create the document.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(document: DocumentRecord) {
    setActionError(null);
    setDeletingId(document.id);
    try {
      await deleteDocument(document.id);
      setDocuments((current) => current.filter((item) => item.id !== document.id));
    } catch (error) {
      setActionError(error instanceof ApiError ? error.message : "Could not delete the document.");
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <main className="mx-auto max-w-7xl px-5 py-10 sm:px-8 sm:py-14">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm font-semibold text-accent">LIBRARY</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight">Documents</h1>
          <p className="mt-2 max-w-2xl text-muted">Manage document details in your organization’s private library.</p>
        </div>
        <button
          type="button"
          onClick={() => {
            setActionError(null);
            setFormOpen((open) => !open);
          }}
          className="rounded-lg bg-accent px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:brightness-110"
        >
          {formOpen ? "Cancel" : "+ Add document"}
        </button>
      </div>

      {actionError && (
        <p className="mt-6 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-fail" role="alert">
          {actionError}
        </p>
      )}

      {formOpen && (
        <section className="mt-7 rounded-xl border border-line bg-white p-5 shadow-sm sm:p-7" aria-labelledby="new-document-heading">
          <h2 id="new-document-heading" className="text-lg font-semibold">Add document details</h2>
          <p className="mt-1 text-sm text-muted">This creates a metadata record. File upload and storage will be added separately.</p>
          <form onSubmit={handleCreate} className="mt-5 grid gap-4 md:grid-cols-2">
            <div className="md:col-span-2">
              <label htmlFor="document-name" className="mb-2 block text-sm font-medium">Name</label>
              <input
                id="document-name"
                value={name}
                onChange={(event) => setName(event.target.value)}
                required
                maxLength={255}
                placeholder="e.g. Employee handbook"
                className="w-full rounded-lg border border-line px-3.5 py-3 text-sm outline-none focus:border-accent focus:ring-4 focus:ring-blue-100"
              />
            </div>
            <div className="md:col-span-2">
              <label htmlFor="document-description" className="mb-2 block text-sm font-medium">Description <span className="font-normal text-muted">(optional)</span></label>
              <textarea
                id="document-description"
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                rows={3}
                maxLength={10_000}
                placeholder="What should teammates know about this document?"
                className="w-full resize-y rounded-lg border border-line px-3.5 py-3 text-sm outline-none focus:border-accent focus:ring-4 focus:ring-blue-100"
              />
            </div>
            <div>
              <label htmlFor="document-mime" className="mb-2 block text-sm font-medium">MIME type <span className="font-normal text-muted">(optional)</span></label>
              <input
                id="document-mime"
                value={mimeType}
                onChange={(event) => setMimeType(event.target.value)}
                maxLength={255}
                placeholder="application/pdf"
                className="w-full rounded-lg border border-line px-3.5 py-3 text-sm outline-none focus:border-accent focus:ring-4 focus:ring-blue-100"
              />
            </div>
            <div>
              <label htmlFor="document-size" className="mb-2 block text-sm font-medium">File size in bytes <span className="font-normal text-muted">(optional)</span></label>
              <input
                id="document-size"
                type="number"
                min={0}
                step={1}
                value={fileSize}
                onChange={(event) => setFileSize(event.target.value)}
                placeholder="0"
                className="w-full rounded-lg border border-line px-3.5 py-3 text-sm outline-none focus:border-accent focus:ring-4 focus:ring-blue-100"
              />
            </div>
            <div className="flex justify-end md:col-span-2">
              <button type="submit" disabled={saving || !name.trim()} className="rounded-lg bg-accent px-5 py-2.5 text-sm font-semibold text-white hover:brightness-110 disabled:cursor-wait disabled:opacity-60">
                {saving ? "Saving…" : "Create document"}
              </button>
            </div>
          </form>
        </section>
      )}

      <section className="mt-8" aria-label="Organization documents">
        {loading ? (
          <div className="rounded-xl border border-line bg-white p-8 text-center text-sm text-muted" role="status">
            Loading documents…
          </div>
        ) : loadError ? (
          <div className="rounded-xl border border-red-200 bg-white p-8 text-center">
            <p className="text-sm text-fail" role="alert">{loadError}</p>
            <button type="button" onClick={() => void refresh()} className="mt-4 rounded-lg border border-line px-4 py-2 text-sm font-semibold hover:bg-slate-50">
              Try again
            </button>
          </div>
        ) : documents.length === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-16 text-center sm:px-12">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-blue-50 text-xl text-accent" aria-hidden="true">▤</div>
            <h2 className="mt-5 text-lg font-semibold">Your library is empty</h2>
            <p className="mx-auto mt-2 max-w-lg text-sm leading-6 text-muted">
              Create a metadata record to start organizing your team’s documents. File upload and storage are not enabled yet.
            </p>
            <button type="button" onClick={() => setFormOpen(true)} className="mt-6 rounded-lg bg-accent px-4 py-2.5 text-sm font-semibold text-white hover:brightness-110">
              Add your first document
            </button>
          </div>
        ) : (
          <ul className="overflow-hidden rounded-xl border border-line bg-white shadow-sm">
            {documents.map((document) => (
              <li key={document.id} className="flex flex-col gap-4 border-b border-line p-5 last:border-b-0 sm:flex-row sm:items-center sm:justify-between sm:px-6">
                <div className="flex min-w-0 items-start gap-4">
                  <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-blue-50 text-accent" aria-hidden="true">▤</div>
                  <div className="min-w-0">
                    <h2 className="truncate font-semibold">{document.name}</h2>
                    {document.description && <p className="mt-1 line-clamp-2 text-sm text-muted">{document.description}</p>}
                    <p className="mt-2 text-xs text-muted">
                      {document.mime_type ?? "Metadata only"}
                      {document.file_size !== null && ` · ${formatBytes(document.file_size)}`}
                      {` · ${document.versions.length} ${document.versions.length === 1 ? "version" : "versions"}`}
                    </p>
                  </div>
                </div>
                <div className="flex shrink-0 items-center justify-between gap-4 sm:justify-end">
                  <div className="text-right">
                    <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium capitalize ${statusStyles[document.status]}`}>
                      {document.status}
                    </span>
                    <p className="mt-1 text-xs text-muted">Updated {formatDate(document.updated_at)}</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => void handleDelete(document)}
                    disabled={deletingId === document.id}
                    aria-label={`Delete ${document.name}`}
                    className="rounded-md border border-line px-3 py-2 text-sm font-medium text-fail hover:bg-red-50 disabled:opacity-60"
                  >
                    {deletingId === document.id ? "Deleting…" : "Delete"}
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <p className="mt-6 text-sm text-muted">
        Need to check your local services? <Link className="font-medium text-accent hover:underline" to="/status">Open system status</Link>
      </p>
    </main>
  );
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(new Date(value));
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let value = bytes;
  let unit = -1;
  do {
    value /= 1024;
    unit += 1;
  } while (value >= 1024 && unit < units.length - 1);
  return `${value.toFixed(value < 10 ? 1 : 0)} ${units[unit]}`;
}
