import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { searchDocuments } from "../api/search";
import { SearchPage } from "./SearchPage";

vi.mock("../api/search", () => ({ searchDocuments: vi.fn() }));

const mockedSearch = vi.mocked(searchDocuments);
const result = {
  document_id: "doc-1", document_name: "Security policy", chunk_id: "chunk-1",
  content: "Report incidents to the security team.", page_number: 4, similarity_score: 0.87,
};

afterEach(() => vi.clearAllMocks());

function renderPage() { return render(<MemoryRouter><SearchPage /></MemoryRouter>); }

describe("SearchPage", () => {
  it("shows relevant snippets and references after searching", async () => {
    mockedSearch.mockResolvedValue({ results: [result] });
    renderPage();
    fireEvent.change(screen.getByLabelText("Search documents"), { target: { value: "incident reporting" } });
    fireEvent.click(screen.getByRole("button", { name: "Search" }));
    expect(await screen.findByText(result.content)).toBeInTheDocument();
    expect(screen.getByText("Page 4 · 87% match")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Security policy" })).toHaveAttribute("href", "/documents#document-doc-1");
  });

  it("shows empty and API failure states", async () => {
    mockedSearch.mockResolvedValueOnce({ results: [] });
    renderPage();
    fireEvent.change(screen.getByLabelText("Search documents"), { target: { value: "unknown topic" } });
    fireEvent.click(screen.getByRole("button", { name: "Search" }));
    expect(await screen.findByText("No matching passages")).toBeInTheDocument();

    mockedSearch.mockRejectedValueOnce(new Error("Search service unavailable"));
    fireEvent.change(screen.getByLabelText("Search documents"), { target: { value: "policy details" } });
    fireEvent.click(screen.getByRole("button", { name: "Search" }));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Search service unavailable"));
  });
});
