import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "../App";
import type { DocumentRecord } from "../types/documents";

const user = {
  id: "a6e7c8dc-0050-4756-a1f5-40d3d8ba2292",
  email: "writer@example.com",
  full_name: "Writer",
  is_active: true,
  created_at: "2026-11-16T00:00:00Z",
};

function apiDocument(
  name: string,
  id = "e6a941eb-8ae8-493d-84e4-09edc64e84c0",
): DocumentRecord {
  return {
    id,
    organization_id: "e86f4428-e648-460f-87e4-5ff880595cc2",
    owner_id: user.id,
    name,
    description: null,
    mime_type: null,
    file_size: null,
    status: "uploaded",
    created_at: "2026-11-16T00:00:00Z",
    updated_at: "2026-11-16T00:00:00Z",
    versions: [
      {
        id: "0d304106-2ea7-4f57-8598-6194d5dc6f6c",
        version_number: 1,
        name,
        description: null,
        mime_type: null,
        file_size: null,
        created_by: user.id,
        created_at: "2026-11-16T00:00:00Z",
      },
    ],
  };
}

function jsonResponse(body: unknown, status = 200) {
  return { ok: status >= 200 && status < 300, status, json: async () => body };
}

afterEach(() => {
  vi.unstubAllGlobals();
  window.sessionStorage.clear();
  window.history.replaceState({}, "", "/");
});

describe("DocumentsPage", () => {
  it("lists, creates, and deletes organization document metadata", async () => {
    window.history.replaceState({}, "", "/documents");
    window.sessionStorage.setItem("securedocs.accessToken", "documents-token");
    const records: DocumentRecord[] = [];
    const fetchMock = vi.fn(async (url: string | URL | Request, init?: RequestInit) => {
      const path = String(url);
      if (path === "/api/v1/auth/me") return jsonResponse(user);
      if (path === "/api/v1/documents" && (!init?.method || init.method === "GET")) {
        return jsonResponse([...records]);
      }
      if (path === "/api/v1/documents" && init?.method === "POST") {
        const payload = JSON.parse(String(init.body)) as {
          name: string;
          description: string | null;
        };
        const created = apiDocument(payload.name);
        created.description = payload.description;
        created.versions[0].description = payload.description;
        records.unshift(created);
        return jsonResponse(created, 201);
      }
      if (path.endsWith(`/api/v1/documents/${records[0]?.id}`) && init?.method === "DELETE") {
        records.shift();
        return { ok: true, status: 204, json: async () => undefined };
      }
      throw new Error(`Unexpected request: ${init?.method ?? "GET"} ${path}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);
    expect(await screen.findByText("Your library is empty")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Add your first document" }));
    fireEvent.change(screen.getByLabelText("Name"), {
      target: { value: "Quarterly report.pdf" },
    });
    fireEvent.change(screen.getByLabelText(/Description/), {
      target: { value: "Q4 performance" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create document" }));

    expect(await screen.findByRole("heading", { name: "Quarterly report.pdf" })).toBeInTheDocument();
    expect(screen.getByText("Q4 performance")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Delete Quarterly report.pdf" }));
    expect(await screen.findByText("Your library is empty")).toBeInTheDocument();

    await waitFor(() => {
      const documentRequests = fetchMock.mock.calls.filter(([url]) =>
        String(url).startsWith("/api/v1/documents"),
      );
      expect(documentRequests.length).toBeGreaterThanOrEqual(3);
    });
    const [, createRequest] = fetchMock.mock.calls.find(
      ([url, init]) => String(url) === "/api/v1/documents" && init?.method === "POST",
    ) as [string, RequestInit];
    expect(JSON.parse(String(createRequest.body))).toEqual({
      name: "Quarterly report.pdf",
      description: "Q4 performance",
      mime_type: null,
      file_size: null,
    });
  });

  it("shows an API error and provides retry when listing documents fails", async () => {
    window.history.replaceState({}, "", "/documents");
    window.sessionStorage.setItem("securedocs.accessToken", "documents-token");
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(user))
      .mockResolvedValueOnce(jsonResponse({ detail: "Database unavailable" }, 503))
      .mockResolvedValueOnce(jsonResponse([]));
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Database unavailable");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Your library is empty")).toBeInTheDocument();
  });
});
