import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ResponseFeedbackBar } from '../ResponseFeedbackBar';

describe('ResponseFeedbackBar', () => {
  it('renders thumbs up and thumbs down buttons', () => {
    render(
      <ResponseFeedbackBar
        attemptId="test-id"
        currentFeedback={null}
        onFeedback={vi.fn()}
      />
    );
    expect(screen.getByTestId('feedback-thumbs-up')).toBeInTheDocument();
    expect(screen.getByTestId('feedback-thumbs-down')).toBeInTheDocument();
  });
});
