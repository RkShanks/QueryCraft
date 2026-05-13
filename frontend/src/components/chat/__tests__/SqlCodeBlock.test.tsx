import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { SqlCodeBlock } from '../SqlCodeBlock';
import { createWrapper } from '../../../test/utils';

vi.mock('shiki', () => ({
  createHighlighter: vi.fn(() =>
    Promise.resolve({
      codeToHtml: vi.fn((code: string) => `<pre data-testid="highlighted-code">${code}</pre>`),
    })
  ),
}));

describe('SqlCodeBlock', () => {
  it('is hidden by default and shows toggle button', () => {
    render(<SqlCodeBlock code="SELECT * FROM users;" />, { wrapper: createWrapper() });
    expect(screen.getByTestId('sql-toggle-btn')).toBeInTheDocument();
    expect(screen.getByText('Show SQL')).toBeInTheDocument();
    expect(screen.queryByTestId('sql-skeleton')).not.toBeInTheDocument();
  });

  it('shows SQL after toggle click and hides again on second click', async () => {
    render(<SqlCodeBlock code="SELECT * FROM users;" />, { wrapper: createWrapper() });

    fireEvent.click(screen.getByTestId('sql-toggle-btn'));
    expect(screen.getByText('Hide SQL')).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.queryByTestId('sql-skeleton')).not.toBeInTheDocument();
      expect(screen.getByTestId('shiki-highlighter')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId('sql-toggle-btn'));
    expect(screen.getByText('Show SQL')).toBeInTheDocument();
    expect(screen.queryByTestId('shiki-highlighter')).not.toBeInTheDocument();
  });
});
