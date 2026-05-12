import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { SqlCodeBlock } from '../SqlCodeBlock';

vi.mock('shiki', () => ({
  createHighlighter: vi.fn(() =>
    Promise.resolve({
      codeToHtml: vi.fn((code: string) => `<pre data-testid="highlighted-code">${code}</pre>`),
    })
  ),
}));

describe('SqlCodeBlock', () => {
  it('renders loading skeleton initially', () => {
    render(<SqlCodeBlock code="SELECT * FROM users;" />);
    expect(screen.getByTestId('sql-skeleton')).toBeInTheDocument();
  });

  it('renders highlighted SQL after Shiki loads', async () => {
    render(<SqlCodeBlock code="SELECT * FROM users;" />);

    await waitFor(() => {
      expect(screen.queryByTestId('sql-skeleton')).not.toBeInTheDocument();
      expect(screen.getByTestId('shiki-highlighter')).toBeInTheDocument();
      expect(screen.getByText('SELECT * FROM users;')).toBeInTheDocument();
    });
  });
});
