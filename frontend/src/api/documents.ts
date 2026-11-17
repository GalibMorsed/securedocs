import type { DocumentPayload, DocumentRecord } from "../types/documents";
import { apiBlobRequest, apiRequest, ApiError, API_BASE_URL, getErrorMessage } from "./client";

export const MAX_UPLOAD_BYTES = Number(
  import.meta.env.VITE_MAX_UPLOAD_BYTES ?? 10 * 1024 * 1024,
);

const SUPPORTED_FILE_TYPES: Record<string, string> = {
  ".pdf": "application/pdf",
  ".txt": "text/plain",
  ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
};

export function validateSelectedFile(file: File): string | null {
  if (file.size === 0) return "Empty files cannot be uploaded.";
  if (file.size > MAX_UPLOAD_BYTES) {
    return `Choose a file smaller than ${formatBytes(MAX_UPLOAD_BYTES)}.`;
  }
  const extension = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
  const expectedType = SUPPORTED_FILE_TYPES[extension];
  if (!expectedType || file.type.toLowerCase() !== expectedType) {
    return "Choose a PDF, plain text, or DOCX file with a matching file type.";
  }
  return null;
}

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

export function uploadDocument(
  file: File,
  description: string,
  onProgress: (percent: number) => void,
): Promise<DocumentRecord> {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    const formData = new FormData();
    formData.append("file", file, file.name);
    if (description.trim()) formData.append("description", description.trim());

    request.open("POST", `${API_BASE_URL}/documents/upload`);
    const token = window.sessionStorage.getItem("securedocs.accessToken");
    if (token) request.setRequestHeader("Authorization", `Bearer ${token}`);

    request.upload.onprogress = (event) => {
      if (event.lengthComputable && event.total > 0) {
        onProgress(Math.min(100, Math.round((event.loaded / event.total) * 100)));
      }
    };
    request.onload = () => {
      const body: unknown = parseJson(request.responseText);
      if (request.status >= 200 && request.status < 300) {
        resolve(body as DocumentRecord);
      } else {
        reject(
          new ApiError(
            request.status,
            getErrorMessage(body, `Upload failed with status ${request.status}`),
            body,
          ),
        );
      }
    };
    request.onerror = () => reject(new ApiError(0, "The upload connection failed. Please retry."));
    request.onabort = () => reject(new ApiError(0, "The upload was cancelled."));
    request.send(formData);
  });
}

export function downloadDocument(id: string): Promise<Blob> {
  return apiBlobRequest(`/documents/${encodeURIComponent(id)}/download`);
}

function parseJson(value: string): unknown {
  try {
    return JSON.parse(value) as unknown;
  } catch {
    return undefined;
  }
}

function formatBytes(value: number): string {
  if (value < 1024) return `${value} B`;
  let amount = value;
  let unit = -1;
  const units = ["KB", "MB", "GB"];
  do {
    amount /= 1024;
    unit += 1;
  } while (amount >= 1024 && unit < units.length - 1);
  return `${amount.toFixed(amount < 10 ? 1 : 0)} ${units[unit]}`;
}
