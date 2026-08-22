import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import HistoryPage from "./HistoryPage";
import { createWrapper } from "../test/utils";

vi.mock("../api/historyApi", () => ({
  listHistory: vi.fn(),
  getHistoryItem: vi.fn(),
}));
import * as historyApi from "../api/historyApi";

function renderPage() {
  return render(<HistoryPage />, { wrapper: createWrapper() });
}

describe("HistoryPage (FR-021,FR-022,FR-023,SC-009)", () => {
  beforeEach(() => vi.clearAllMocks());

  it("loads history and renders the list", async () => {
    vi.mocked(historyApi.listHistory).mockResolvedValueOnce({
      items: [
        { id: "1", question_text: "Q1", generated_sql: "SELECT 1", accepted_at: "2026-05-11T00:00:00Z" },
      ],
      total: 1,
      next_cursor: null,
    });
    renderPage();
    await waitFor(() => expect(screen.getByText("Q1")).toBeInTheDocument());
  });

  it("clicking a list row shows its detail (FR-023)", async () => {
    vi.mocked(historyApi.listHistory).mockResolvedValueOnce({
      items: [{ id: "1", question_text: "Q1", generated_sql: "SELECT 1", accepted_at: "2026-05-11T00:00:00Z" }],
      total: 1,
      next_cursor: null,
    });
    vi.mocked(historyApi.getHistoryItem).mockResolvedValueOnce({
      id: "1", question_text: "Q1", generated_sql: "SELECT 1", accepted_at: "2026-05-11T00:00:00Z", llm_provider: "openai", database_connection_id: "conn-1",
    });
    renderPage();
    await waitFor(() => screen.getByText("Q1"));
    fireEvent.click(screen.getByText("Q1"));
    await waitFor(() => {
      const detail = screen.getByTestId("history-detail");
      expect(detail).toHaveTextContent("SELECT 1");
    });
  });

  it("shows empty state when no items (FR-021)", async () => {
    vi.mocked(historyApi.listHistory).mockResolvedValueOnce({ items: [], total: 0, next_cursor: null });
    renderPage();
    await waitFor(() => expect(screen.getByText(/no history yet/i)).toBeInTheDocument());
  });

  it("sends the debounced filter to the server (IS-GAP-032)", async () => {
    const calls: Array<{ search?: string }> = [];
    vi.mocked(historyApi.listHistory).mockImplementation(async (params?) => {
      calls.push({ search: params?.search });
      const searchParam = params?.search;
      if (searchParam === "revenue") {
        return {
          items: [
            { id: "2", question_text: "Revenue top", generated_sql: "SELECT ... FROM payment", accepted_at: "2026-05-10T00:00:00Z" },
          ],
          total: 1,
          next_cursor: null,
        };
      }
      return {
        items: [
          { id: "1", question_text: "Customer count", generated_sql: "SELECT COUNT(*) FROM customer", accepted_at: "2026-05-11T00:00:00Z" },
        ],
        total: 1,
        next_cursor: null,
      };
    });
    renderPage();
    await waitFor(() => screen.getByText("Customer count"));
    fireEvent.change(screen.getByPlaceholderText(/filter/i), { target: { value: "revenue" } });
    // Debounce delay is 300ms; wait for it with real timers
    await new Promise((resolve) => setTimeout(resolve, 350));
    await waitFor(() => expect(screen.getByText("Revenue top")).toBeInTheDocument());
    expect(calls.some((call) => call.search === "revenue")).toBe(true);
  });

  it("wires pagination props to HistoryList (O-016)", async () => {
    vi.mocked(historyApi.listHistory)
      .mockResolvedValueOnce({
        items: [{ id: "1", question_text: "Q1", generated_sql: "SELECT 1", accepted_at: "2026-05-11T00:00:00Z" }],
        total: 1,
        next_cursor: "cursor-1",
      })
      .mockResolvedValueOnce({
        items: [{ id: "2", question_text: "Q2", generated_sql: "SELECT 2", accepted_at: "2026-05-10T00:00:00Z" }],
        total: 1,
        next_cursor: null,
      });
    renderPage();
    await waitFor(() => screen.getByText("Q1"));
    const loadMore = screen.getByRole("button", { name: /load more/i });
    expect(loadMore).toBeInTheDocument();
    fireEvent.click(loadMore);
    await waitFor(() => expect(screen.getByText("Q2")).toBeInTheDocument());
  });
});
