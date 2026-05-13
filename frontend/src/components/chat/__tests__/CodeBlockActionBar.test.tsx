import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { CodeBlockActionBar } from '../CodeBlockActionBar';

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
});
