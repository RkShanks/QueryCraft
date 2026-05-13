import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
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

  it('calls onFeedback with +1 when thumbs up is clicked and no feedback exists', () => {
    const onFeedback = vi.fn();
    render(
      <ResponseFeedbackBar
        attemptId="attempt-1"
        currentFeedback={null}
        onFeedback={onFeedback}
      />
    );
    fireEvent.click(screen.getByTestId('feedback-thumbs-up'));
    expect(onFeedback).toHaveBeenCalledWith('attempt-1', 1);
  });

  it('calls onFeedback with -1 when thumbs down is clicked and no feedback exists', () => {
    const onFeedback = vi.fn();
    render(
      <ResponseFeedbackBar
        attemptId="attempt-1"
        currentFeedback={null}
        onFeedback={onFeedback}
      />
    );
    fireEvent.click(screen.getByTestId('feedback-thumbs-down'));
    expect(onFeedback).toHaveBeenCalledWith('attempt-1', -1);
  });

  it('calls onFeedback with 0 when active thumbs up is clicked again', () => {
    const onFeedback = vi.fn();
    render(
      <ResponseFeedbackBar
        attemptId="attempt-1"
        currentFeedback={1}
        onFeedback={onFeedback}
      />
    );
    fireEvent.click(screen.getByTestId('feedback-thumbs-up'));
    expect(onFeedback).toHaveBeenCalledWith('attempt-1', 0);
  });

  it('calls onFeedback with 0 when active thumbs down is clicked again', () => {
    const onFeedback = vi.fn();
    render(
      <ResponseFeedbackBar
        attemptId="attempt-1"
        currentFeedback={-1}
        onFeedback={onFeedback}
      />
    );
    fireEvent.click(screen.getByTestId('feedback-thumbs-down'));
    expect(onFeedback).toHaveBeenCalledWith('attempt-1', 0);
  });

  it('shows saved label when thumbs up is active and saved is true', () => {
    render(
      <ResponseFeedbackBar
        attemptId="attempt-1"
        currentFeedback={1}
        saved={true}
        onFeedback={vi.fn()}
      />
    );
    expect(screen.getByTestId('feedback-saved-label')).toBeInTheDocument();
  });

  it('does not show saved label when thumbs up is active but not saved', () => {
    render(
      <ResponseFeedbackBar
        attemptId="attempt-1"
        currentFeedback={1}
        saved={false}
        onFeedback={vi.fn()}
      />
    );
    expect(screen.queryByTestId('feedback-saved-label')).not.toBeInTheDocument();
  });
});
