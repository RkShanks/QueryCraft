import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { CodeBlockActionBar } from '../CodeBlockActionBar';

const mockWriteText = vi.fn();

beforeEach(() => {
  Object.defineProperty(navigator, 'clipboard', {
    value: { writeText: mockWriteText },
    writable: true,
    configurable: true,
  });
});

afterEach(() => {
  vi.clearAllMocks();
});

describe('CodeBlockActionBar', () => {
  it('renders copy and regenerate buttons', () => {
    render(
      <CodeBlockActionBar
        sql="SELECT 1;"
        attemptId="test-id"
        onRegenerate={vi.fn()}
      />
    );
    expect(screen.getByTestId('action-copy')).toBeInTheDocument();
    expect(screen.getByTestId('action-regenerate')).toBeInTheDocument();
    // thumbs buttons removed in Wave 10.4
    expect(screen.queryByTestId('action-thumbs-down')).not.toBeInTheDocument();
  });

  it('calls clipboard.writeText when copy button is clicked', async () => {
    mockWriteText.mockResolvedValueOnce(undefined);
    render(
      <CodeBlockActionBar
        sql="SELECT 1;"
        attemptId="test-id"
        onRegenerate={vi.fn()}
      />
    );
    fireEvent.click(screen.getByTestId('action-copy'));
    expect(mockWriteText).toHaveBeenCalledWith('SELECT 1;');
  });

  it('calls onRegenerate when regenerate is clicked', () => {
    const onRegenerate = vi.fn();
    render(
      <CodeBlockActionBar
        sql="SELECT 1;"
        attemptId="attempt-42"
        onRegenerate={onRegenerate}
      />
    );
    fireEvent.click(screen.getByTestId('action-regenerate'));
    expect(onRegenerate).toHaveBeenCalledWith('attempt-42');
  });
});
