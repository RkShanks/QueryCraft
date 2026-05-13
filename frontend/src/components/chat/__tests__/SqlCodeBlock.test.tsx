import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { SqlCodeBlock } from '../SqlCodeBlock';

vi.mock('shiki', () => ({
  createHighlighter: vi.fn(() =>
    Promise.resolve({
      codeToHtml: vi.fn((code: string) => `<pre data-testid="highlighted-code">${code}</pre>`),
    })
  ),
}));

describe('SqlCodeBlock', () => {
  it('is hidden by default and shows toggle button', () => {
    render(<SqlCodeBlock code="SELECT * FROM users;" />);
    expect(screen.getByTestId('sql-toggle-btn')).toBeInTheDocument();
    expect(screen.getByText('Show SQL')).toBeInTheDocument();
    expect(screen.queryByTestId('sql-skeleton')).not.toBeInTheDocument();
  });

  it('renders loading skeleton and then code when toggle is clicked', async () => {
    render(<SqlCodeBlock code="SELECT * FROM users;" />);
    
    fireEvent.click(screen.getByTestId('sql-toggle-btn'));
    
    // Skeleton should show immediately
    expect(screen.getByTestId('sql-skeleton')).toBeInTheDocument();
    expect(screen.getByText('Hide SQL')).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.queryByTestId('sql-skeleton')).not.toBeInTheDocument();
      expect(screen.getByTestId('shiki-highlighter')).toBeInTheDocument();
      expect(screen.getByText('SELECT * FROM users;')).toBeInTheDocument();
    });
    
    // Click again to hide
    fireEvent.click(screen.getByTestId('sql-toggle-btn'));
    expect(screen.getByText('Show SQL')).toBeInTheDocument();
    expect(screen.queryByTestId('shiki-highlighter')).not.toBeInTheDocument();
  });
});
