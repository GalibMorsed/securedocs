import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { listConversations, streamChat } from "../api/chat";
import { ChatPage } from "./ChatPage";

vi.mock("../api/chat", () => ({
  listConversations: vi.fn(),
  getConversation: vi.fn(),
  streamChat: vi.fn(),
}));

const mockList = vi.mocked(listConversations);
const mockStream = vi.mocked(streamChat);
const citation = {
  document_id: "document-1", document_name: "Security policy", chunk_id: "chunk-1",
  page_number: 3, source_text: "Report incidents to the security team.", similarity_score: 0.84,
};

afterEach(() => vi.clearAllMocks());

describe("ChatPage", () => {
  it("streams a grounded response and displays backend source citations", async () => {
    mockList.mockResolvedValue([]);
    mockStream.mockImplementation(async (_payload, onEvent) => {
      onEvent({ type: "start", conversation_id: "conversation-1", user_message_id: "user-1" });
      onEvent({ type: "sources", citations: [citation], no_relevant_sources: false });
      onEvent({ type: "delta", text: "The policy says to report incidents promptly." });
      onEvent({ type: "done", conversation_id: "conversation-1", message_id: "assistant-1", answer: "The policy says to report incidents promptly.", citations: [citation], no_relevant_sources: false });
    });
    render(<MemoryRouter><ChatPage /></MemoryRouter>);
    fireEvent.change(screen.getByLabelText("Ask a question about your documents"), { target: { value: "How do I report an incident?" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(await screen.findByText("The policy says to report incidents promptly.")).toBeInTheDocument();
    expect(screen.getByText("Sources verified by SecureDocs")).toBeInTheDocument();
    expect(screen.getByText(citation.source_text)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Security policy · Page 3" })).toHaveAttribute("href", "/documents#document-document-1");
  });

  it("shows an honest answer when retrieval finds no sources", async () => {
    mockList.mockResolvedValue([]);
    mockStream.mockImplementation(async (_payload, onEvent) => {
      onEvent({ type: "start", conversation_id: "conversation-2", user_message_id: "user-2" });
      onEvent({ type: "sources", citations: [], no_relevant_sources: true });
      onEvent({ type: "delta", text: "I couldn't find relevant information in your organization's processed documents." });
      onEvent({ type: "done", conversation_id: "conversation-2", message_id: "assistant-2", answer: "I couldn't find relevant information in your organization's processed documents.", citations: [], no_relevant_sources: true });
    });
    render(<MemoryRouter><ChatPage /></MemoryRouter>);
    fireEvent.change(screen.getByLabelText("Ask a question about your documents"), { target: { value: "What is the unknown policy?" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() => expect(screen.getByText(/I couldn't find relevant information/)).toBeInTheDocument());
    expect(screen.queryByText("Sources verified by SecureDocs")).not.toBeInTheDocument();
  });
});
