import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { ApiError } from "../api/client";
import {
  deleteDocument,
  downloadDocument,
  listDocuments,
  MAX_UPLOAD_BYTES,
  retryDocumentProcessing,
  uploadDocument,
  validateSelectedFile,
} from "../api/documents";
import type { DocumentRecord, DocumentStatus } from "../types/documents";

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
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [description, setDescription] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadFailed, setUploadFailed] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [retryingId, setRetryingId] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  const refresh = useCallback(async (showLoading = true) => {
    if (showLoading) setLoading(true);
    setLoadError(null);
    try {
      setDocuments(await listDocuments());
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : "Could not load documents.");
    } finally {
      if (showLoading) setLoading(false);
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);
  useEffect(() => {
    if (!loading && window.location.hash.startsWith("#document-")) {
      document.getElementById(decodeURIComponent(window.location.hash.slice(1)))?.scrollIntoView({ block: "center" });
    }
  }, [loading, documents]);

  const hasPendingFiles = documents.some(
    (document) => document.has_file && (document.status === "uploaded" || document.status === "processing"),
  );
  useEffect(() => {
    if (!hasPendingFiles) return;
    const interval = window.setInterval(() => { void refresh(false); }, 2500);
    return () => window.clearInterval(interval);
  }, [hasPendingFiles, refresh]);

  function handleFileChange(file: File | null) {
    setActionError(null);
    setUploadFailed(false);
    setUploadProgress(0);
    setSelectedFile(file);
    setFileError(file ? validateSelectedFile(file) : null);
  }

  async function handleUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedFile || fileError || uploading) return;
    setActionError(null);
    setUploading(true);
    setUploadFailed(false);
    setUploadProgress(0);
    try {
      const uploaded = await uploadDocument(selectedFile, description, setUploadProgress);
      setDocuments((current) => [uploaded, ...current]);
      setSelectedFile(null);
      setDescription("");
      setUploadProgress(100);
      if (fileInput.current) fileInput.current.value = "";
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Upload failed. Please retry.");
      setUploadFailed(true);
    } finally {
      setUploading(false);
    }
  }

  async function handleDownload(document: DocumentRecord) {
    setActionError(null);
    setDownloadingId(document.id);
    try {
      const blob = await downloadDocument(document.id);
      const url = URL.createObjectURL(blob);
      const anchor = window.document.createElement("a");
      anchor.href = url;
      anchor.download = document.name;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Could not download this document.");
    } finally {
      setDownloadingId(null);
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

  async function handleRetry(document: DocumentRecord) {
    setActionError(null);
    setRetryingId(document.id);
    try {
      const retried = await retryDocumentProcessing(document.id);
      setDocuments((current) => current.map((item) => item.id === document.id ? retried : item));
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Could not retry document processing.");
    } finally {
      setRetryingId(null);
    }
  }

  return (
    <main className="mx-auto max-w-7xl px-5 py-10 sm:px-8 sm:py-14">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm font-semibold text-accent">LIBRARY</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight">Documents</h1>
          <p className="mt-2 max-w-2xl text-muted">Secure files for your organization, ready to download whenever you need them.</p>
        </div>
      </div>

      {actionError && <p className="mt-6 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-fail" role="alert">{actionError}</p>}

      <section className="mt-7 rounded-xl border border-line bg-white p-5 shadow-sm sm:p-7" aria-labelledby="upload-document-heading">
        <h2 id="upload-document-heading" className="text-lg font-semibold">Upload a document</h2>
        <p className="mt-1 text-sm text-muted">PDF, plain text, or DOCX up to {formatBytes(MAX_UPLOAD_BYTES)}.</p>
        <form onSubmit={handleUpload} className="mt-5 grid gap-4 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto] md:items-end">
          <div>
            <label htmlFor="document-file" className="mb-2 block text-sm font-medium">File</label>
            <input
              ref={fileInput}
              id="document-file"
              type="file"
              accept=".pdf,.txt,.docx,application/pdf,text/plain,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
              disabled={uploading}
              onChange={(event) => handleFileChange(event.target.files?.[0] ?? null)}
              className="block w-full rounded-lg border border-line px-3 py-2.5 text-sm file:mr-3 file:rounded-md file:border-0 file:bg-blue-50 file:px-3 file:py-1.5 file:font-medium file:text-accent"
              aria-describedby={fileError ? "document-file-error" : "document-file-help"}
            />
            <p id="document-file-help" className="mt-1.5 text-xs text-muted">{selectedFile ? `${selectedFile.name} · ${formatBytes(selectedFile.size)}` : "Choose a supported file."}</p>
            {fileError && <p id="document-file-error" className="mt-1.5 text-sm text-fail" role="alert">{fileError}</p>}
          </div>
          <div>
            <label htmlFor="document-description" className="mb-2 block text-sm font-medium">Description <span className="font-normal text-muted">(optional)</span></label>
            <input
              id="document-description"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              maxLength={10_000}
              disabled={uploading}
              placeholder="What is this document about?"
              className="w-full rounded-lg border border-line px-3.5 py-3 text-sm outline-none focus:border-accent focus:ring-4 focus:ring-blue-100"
            />
          </div>
          <button type="submit" disabled={!selectedFile || Boolean(fileError) || uploading} className="rounded-lg bg-accent px-5 py-3 text-sm font-semibold text-white shadow-sm hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60">
            {uploading ? "Uploading…" : uploadFailed ? "Retry upload" : "Upload file"}
          </button>
        </form>
        {uploading && (
          <div className="mt-4" role="status" aria-live="polite">
            <div className="mb-1 flex justify-between text-xs text-muted"><span>Uploading {selectedFile?.name}</span><span>{uploadProgress}%</span></div>
            <div className="h-2 overflow-hidden rounded-full bg-slate-100" role="progressbar" aria-label="Upload progress" aria-valuemin={0} aria-valuemax={100} aria-valuenow={uploadProgress}>
              <div className="h-full rounded-full bg-accent transition-[width]" style={{ width: `${uploadProgress}%` }} />
            </div>
          </div>
        )}
      </section>

      <section className="mt-8" aria-label="Organization documents">
        {loading ? <div className="rounded-xl border border-line bg-white p-8 text-center text-sm text-muted" role="status">Loading documents…</div>
          : loadError ? <div className="rounded-xl border border-red-200 bg-white p-8 text-center"><p className="text-sm text-fail" role="alert">{loadError}</p><button type="button" onClick={() => void refresh()} className="mt-4 rounded-lg border border-line px-4 py-2 text-sm font-semibold hover:bg-slate-50">Try again</button></div>
            : documents.length === 0 ? <div className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-16 text-center sm:px-12"><div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-blue-50 text-xl text-accent" aria-hidden="true">▤</div><h2 className="mt-5 text-lg font-semibold">Your library is empty</h2><p className="mx-auto mt-2 max-w-lg text-sm leading-6 text-muted">Upload a document to start building your organization’s private library.</p></div>
              : <ul className="overflow-hidden rounded-xl border border-line bg-white shadow-sm">
                {documents.map((document) => (
                  <li id={`document-${document.id}`} key={document.id} className="flex flex-col gap-4 border-b border-line p-5 last:border-b-0 sm:flex-row sm:items-center sm:justify-between sm:px-6">
                    <div className="flex min-w-0 items-start gap-4"><div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-blue-50 text-accent" aria-hidden="true">▤</div><div className="min-w-0"><h2 className="truncate font-semibold">{document.name}</h2>{document.description && <p className="mt-1 line-clamp-2 text-sm text-muted">{document.description}</p>}{document.processing_error && <p className="mt-2 text-sm text-fail" role="status">{document.processing_error}</p>}<p className="mt-2 text-xs text-muted">{document.mime_type ?? "Metadata only"}{document.file_size !== null && ` · ${formatBytes(document.file_size)}`}{` · ${document.versions.length} ${document.versions.length === 1 ? "version" : "versions"}`}</p></div></div>
                    <div className="flex shrink-0 items-center justify-between gap-3 sm:justify-end"><div className="text-right"><span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium capitalize ${statusStyles[document.status]}`}>{document.status}</span><p className="mt-1 text-xs text-muted">Updated {formatDate(document.updated_at)}</p></div>{canRetryProcessing(document) && document.has_file && <button type="button" onClick={() => void handleRetry(document)} disabled={retryingId === document.id} aria-label={`Retry processing ${document.name}`} className="rounded-md border border-line px-3 py-2 text-sm font-medium text-accent hover:bg-blue-50 disabled:opacity-60">{retryingId === document.id ? "Retrying…" : "Retry"}</button>}{document.has_file && <button type="button" onClick={() => void handleDownload(document)} disabled={downloadingId === document.id} aria-label={`Download ${document.name}`} className="rounded-md border border-line px-3 py-2 text-sm font-medium text-accent hover:bg-blue-50 disabled:opacity-60">{downloadingId === document.id ? "Downloading…" : "Download"}</button>}<button type="button" onClick={() => void handleDelete(document)} disabled={deletingId === document.id} aria-label={`Delete ${document.name}`} className="rounded-md border border-line px-3 py-2 text-sm font-medium text-fail hover:bg-red-50 disabled:opacity-60">{deletingId === document.id ? "Deleting…" : "Delete"}</button></div>
                  </li>
                ))}
              </ul>}
      </section>
      <p className="mt-6 text-sm text-muted">Need to check your local services? <Link className="font-medium text-accent hover:underline" to="/status">Open system status</Link></p>
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
  do { value /= 1024; unit += 1; } while (value >= 1024 && unit < units.length - 1);
  return `${value.toFixed(value < 10 ? 1 : 0)} ${units[unit]}`;
}

function canRetryProcessing(document: DocumentRecord): boolean {
  if (document.status === "failed") return true;
  if (document.status !== "processing") return false;
  if (!document.processing_started_at) return true;
  const startedAt = new Date(document.processing_started_at).getTime();
  return Number.isFinite(startedAt) && Date.now() - startedAt > 15 * 60 * 1000;
}
