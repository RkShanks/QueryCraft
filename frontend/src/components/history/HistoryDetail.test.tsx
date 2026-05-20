import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { HistoryDetail } from "./HistoryDetail";

const sample = {
  id: "abc-123",
  question_text: "Total customers?",
  generated_sql: "SELECT COUNT(*) FROM customer",
  accepted_at: "2026-05-11T10:00:00Z",
  llm_provider: "openai",
  database_connection_id: "conn-1",
};

const sampleWithResult = {
  ...sample,
  result_columns: [{ name: "count", type: "integer" }],
  result_rows: [[42]],
  result_row_count: 1,
};

function setup(item: typeof sample | null, opts: { isLoading?: boolean; error?: Error | null } = {}) {
  return render(
    <HistoryDetail item={item} isLoading={opts.isLoading} error={opts.error} />
  );
}

describe("HistoryDetail (FR-023, SC-009, T-465)", () => {
  it("renders question, sql, llm_provider, database_connection_id, accepted_at when item is provided", () => {
    setup(sample);
    expect(screen.getByText(/total customers/i)).toBeInTheDocument();
    expect(screen.getByText(/SELECT COUNT/)).toBeInTheDocument();
    expect(screen.getByText("openai")).toBeInTheDocument();
    expect(screen.getByText("conn-1")).toBeInTheDocument();
    // accepted_at is rendered in a human-readable format; just check the date portion appears
    expect(screen.getByText(/2026/)).toBeInTheDocument();
  });

  it("renders result table when result_columns and result_rows are present", () => {
    setup(sampleWithResult);
    expect(screen.getByText("count")).toBeInTheDocument();
    expect(screen.getByText("42")).toBeInTheDocument();
    expect(screen.getByTestId("result-table")).toBeInTheDocument();
  });

  it("does not render result table when result_columns is null", () => {
    setup(sample);
    expect(screen.queryByTestId("result-table")).not.toBeInTheDocument();
  });

  it("renders loading state when isLoading=true and item is null", () => {
    setup(null, { isLoading: true });
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it("renders error state when error is provided", () => {
    setup(null, { error: new Error("network") });
    expect(screen.getByText(/failed to load/i)).toBeInTheDocument();
  });

  it("renders empty state when item is null and not loading", () => {
    setup(null);
    expect(screen.getByText(/no item selected|select an item/i)).toBeInTheDocument();
  });

  it("renders SQL in a <code> or <pre> element for proper formatting (SC-009)", () => {
    const { container } = setup(sample);
    const codeEl = container.querySelector("pre, code");
    expect(codeEl).not.toBeNull();
    expect(codeEl?.textContent).toContain("SELECT COUNT(*)");
  });

  it("renders connection metadata badge when database_connection_id is present (T-465)", () => {
    setup(sample);
    expect(screen.getByTestId("history-detail-meta")).toBeInTheDocument();
    expect(screen.getByTestId("history-detail-meta")).toHaveTextContent("conn-1");
  });

  it("does not render connection metadata badge when database_connection_id is absent (T-465)", () => {
    const withoutConn = { ...sample, database_connection_id: null };
    setup(withoutConn);
    expect(screen.queryByTestId("history-detail-meta")).not.toBeInTheDocument();
  });
});
