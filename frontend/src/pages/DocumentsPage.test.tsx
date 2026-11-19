import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "../App";
import type { DocumentRecord } from "../types/documents";

const api = vi.hoisted(() => ({
  listDocuments: vi.fn(),
  uploadDocument: vi.fn(),
  deleteDocument: vi.fn(),
  downloadDocument: vi.fn(),
  retryDocumentProcessing: vi.fn(),
}));

vi.mock("../api/documents", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../api/documents")>()),
  ...api,
}));

const user = { id: "a6e7c8dc-0050-4756-a1f5-40d3d8ba2292", email: "writer@example.com", full_name: "Writer", is_active: true, created_at: "2026-11-16T00:00:00Z" };

function apiDocument(name: string, has_file = true): DocumentRecord {
  return {
    id: "e6a941eb-8ae8-493d-84e4-09edc64e84c0",
    organization_id: "e86f4428-e648-460f-87e4-5ff880595cc2",
    owner_id: user.id,
    name,
    has_file,
    description: "",
    mime_type: "text/plain",
    file_size: 12,
    status: "uploaded",
    processing_started_at: null,
    processed_at: null,
    processing_error: null,
    created_at: "2026-11-16T00:00:00Z",
    updated_at: "2026-11-16T00:00:00Z",
    versions: [{ id: "0d304106-2ea7-4f57-8598-6194d5dc6f6c", version_number: 1, name, description: null, mime_type: "text/plain", file_size: 12, created_by: user.id, created_at: "2026-11-16T00:00:00Z" }],
  };
}

function jsonResponse(body: unknown, status = 200) {
  return { ok: status >= 200 && status < 300, status, json: async () => body };
}

beforeEach(() => {
  vi.clearAllMocks();
  window.history.replaceState({}, "", "/documents");
  window.sessionStorage.setItem("securedocs.accessToken", "documents-token");
  api.listDocuments.mockResolvedValue([]);
  api.deleteDocument.mockResolvedValue(undefined);
  api.downloadDocument.mockResolvedValue(new Blob(["document"]));
  api.retryDocumentProcessing.mockImplementation(async (id: string) => {
    const retried = apiDocument("reprocessed.txt");
    retried.id = id;
    return retried;
  });
  vi.stubGlobal("fetch", vi.fn(async (url: string | URL | Request) => {
    if (String(url) === "/api/v1/auth/me") return jsonResponse(user);
    throw new Error(`Unexpected request: ${String(url)}`);
  }));
});

afterEach(() => {
  vi.unstubAllGlobals();
  window.sessionStorage.clear();
  window.history.replaceState({}, "", "/");
});

describe("DocumentsPage uploads", () => {
  it("shows validation errors for unsupported files", async () => {
    render(<App />);
    await screen.findByText("Your library is empty");
    const input = screen.getByLabelText("File") as HTMLInputElement;
    const file = new File(["bad"], "script.exe", { type: "application/octet-stream" });
    fireEvent.change(input, { target: { files: [file] } });
    expect(await screen.findByRole("alert")).toHaveTextContent("Choose a PDF, plain text, DOCX, PNG, JPEG, or TIFF file");
    expect(screen.getByRole("button", { name: "Upload file" })).toBeDisabled();
  });

  it("uploads selected files and displays the returned document with download action", async () => {
    const uploaded = apiDocument("notes.txt");
    api.uploadDocument.mockImplementation(async (_file: File, _description: string, progress: (n: number) => void) => {
      progress(100);
      return uploaded;
    });
    render(<App />);
    await screen.findByText("Your library is empty");
    fireEvent.change(screen.getByLabelText("File"), { target: { files: [new File(["notes"], "notes.txt", { type: "text/plain" })] } });
    fireEvent.change(screen.getByLabelText(/Description/), { target: { value: "Team notes" } });
    fireEvent.click(screen.getByRole("button", { name: "Upload file" }));

    expect(await screen.findByRole("heading", { name: "notes.txt" })).toBeInTheDocument();
    expect(api.uploadDocument).toHaveBeenCalledWith(expect.objectContaining({ name: "notes.txt" }), "Team notes", expect.any(Function));
    expect(screen.getByRole("button", { name: "Download notes.txt" })).toBeInTheDocument();
    expect(screen.getByLabelText("File")).toHaveValue("");
  });

  it("shows upload progress, retains the file, and offers retry after an API failure", async () => {
    let rejectUpload: (error: Error) => void = () => undefined;
    api.uploadDocument.mockImplementation((_file: File, _description: string, progress: (n: number) => void) => {
      progress(42);
      return new Promise((_resolve, reject) => { rejectUpload = reject; });
    });
    render(<App />);
    await screen.findByText("Your library is empty");
    const file = new File(["notes"], "notes.txt", { type: "text/plain" });
    fireEvent.change(screen.getByLabelText("File"), { target: { files: [file] } });
    fireEvent.click(screen.getByRole("button", { name: "Upload file" }));
    expect(await screen.findByRole("progressbar")).toHaveAttribute("aria-valuenow", "42");
    expect(screen.getByRole("button", { name: "Uploading…" })).toBeDisabled();
    rejectUpload(new Error("Storage unavailable"));
    expect(await screen.findByRole("alert")).toHaveTextContent("Storage unavailable");
    expect(screen.getByRole("button", { name: "Retry upload" })).toBeEnabled();
    expect(screen.getByText("notes.txt · 5 B")).toBeInTheDocument();
  });

  it("retries document loading after an API failure", async () => {
    api.listDocuments.mockRejectedValueOnce(new Error("Database unavailable")).mockResolvedValueOnce([]);
    render(<App />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Database unavailable");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Your library is empty")).toBeInTheDocument();
    await waitFor(() => expect(api.listDocuments).toHaveBeenCalledTimes(2));
  });

  it("shows a safe processing failure and allows a retry", async () => {
    const failed = apiDocument("empty.txt");
    failed.status = "failed";
    failed.processing_error = "No searchable text was found in this document.";
    api.listDocuments.mockResolvedValue([failed]);
    render(<App />);

    expect(await screen.findByText("No searchable text was found in this document.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Retry processing empty.txt" }));
    await waitFor(() => expect(api.retryDocumentProcessing).toHaveBeenCalledWith(failed.id));
    expect(await screen.findByText("uploaded", { exact: false })).toBeInTheDocument();
  });
});
