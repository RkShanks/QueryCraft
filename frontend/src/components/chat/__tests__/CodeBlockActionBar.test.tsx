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
  it('renders copy, regenerate, and thumbs down buttons', () => {
    render(
      <CodeBlockActionBar
        sql="SELECT 1;"
        attemptId="test-id"
        onRegenerate={vi.fn()}
        onFeedback={vi.fn()}
      />
    );
    expect(screen.getByTestId('action-copy')).toBeInTheDocument();
    expect(screen.getByTestId('action-regenerate')).toBeInTheDocument();
    expect(screen.getByTestId('action-thumbs-down')).toBeInTheDocument();
  });

  it('calls clipboard.writeText when copy button is clicked', async () => {
    mockWriteText.mockResolvedValueOnce(undefined);
    render(
      <CodeBlockActionBar
        sql="SELECT 1;"
        attemptId="test-id"
        onRegenerate={vi.fn()}
        onFeedback={vi.fn()}
      />
    );
    fireEvent.click(screen.getByTestId('action-copy'));
    expect(mockWriteText).toHaveBeenCalledWith('SELECT 1;');
  });

  it('calls onFeedback(-1) and onRegenerate when regenerate is clicked', () => {
    const onFeedback = vi.fn();
    const onRegenerate = vi.fn();
    render(
      <CodeBlockActionBar
        sql="SELECT 1;"
        attemptId="attempt-42"
        onRegenerate={onRegenerate}
        onFeedback={onFeedback}
      />
    );
    fireEvent.click(screen.getByTestId('action-regenerate'));
    expect(onFeedback).toHaveBeenCalledWith('attempt-42', -1);
    expect(onRegenerate).toHaveBeenCalledWith('attempt-42');
  });

  it('calls onFeedback(-1) when thumbs down is clicked', () => {
    const onFeedback = vi.fn();
    render(
      <CodeBlockActionBar
        sql="SELECT 1;"
        attemptId="attempt-42"
        onRegenerate={vi.fn()}
        onFeedback={onFeedback}
      />
    );
    fireEvent.click(screen.getByTestId('action-thumbs-down'));
    expect(onFeedback).toHaveBeenCalledWith('attempt-42', -1);
  });
});
