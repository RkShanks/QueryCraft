import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { UndoToast } from '../UndoToast';

vi.mock('../../../hooks/useSessions', () => ({
  useDeleteSession: vi.fn(),
}));

import { useDeleteSession } from '../../../hooks/useSessions';
import { resetSessionDeletionLifecycle } from '../../../sessionDeletionLifecycle';

const mockMutate = vi.fn();

function setup(props: Partial<React.ComponentProps<typeof UndoToast>> = {}) {
  const defaultItem = {
    id: 'toast-1',
    sessionId: 'sess-123',
    message: 'Delete session?',
  };

  return render(
    <UndoToast
      item={defaultItem}
      onUndo={vi.fn()}
      onDeleteStarted={vi.fn(() => true)}
      onDeleteFailed={vi.fn()}
      onExpired={vi.fn()}
      {...props}
    />
  );
}

describe('UndoToast', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    resetSessionDeletionLifecycle();
    (useDeleteSession as ReturnType<typeof vi.fn>).mockReturnValue({
      mutate: mockMutate,
    });
    mockMutate.mockClear();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('renders message and undo button', () => {
    setup();
    expect(screen.getByText('Delete session?')).toBeInTheDocument();
    expect(screen.getByText('Undo')).toBeInTheDocument();
  });

  it('fires DELETE after 5 seconds and stays mounted until DELETE succeeds', () => {
    const onExpired = vi.fn();
    setup({ onExpired });

    expect(mockMutate).not.toHaveBeenCalled();

    act(() => {
      vi.advanceTimersByTime(5000);
    });

    expect(mockMutate).toHaveBeenCalledWith(
      'sess-123',
      expect.objectContaining({ onSuccess: expect.any(Function), onError: expect.any(Function) })
    );
    expect(onExpired).not.toHaveBeenCalled();

    act(() => {
      mockMutate.mock.calls[0][1].onSuccess();
    });
    expect(onExpired).toHaveBeenCalledTimes(1);
  });

  it('cancels timer on Undo (API never fires)', () => {
    const onUndo = vi.fn();
    setup({ onUndo });

    fireEvent.click(screen.getByText('Undo'));

    act(() => {
      vi.advanceTimersByTime(5000);
    });

    expect(mockMutate).not.toHaveBeenCalled();
    expect(onUndo).toHaveBeenCalled();
  });

  it('progress bar decreases over time', () => {
    setup();

    const progressBar = screen.getByTestId('undo-progress-toast-1');
    const initialWidth = progressBar.style.width;
    expect(initialWidth).toBe('100%');

    act(() => {
      vi.advanceTimersByTime(2500);
    });

    const midWidth = progressBar.style.width;
    expect(parseFloat(midWidth)).toBeLessThan(100);
  });

  it('does not fire DELETE twice if timer expires', () => {
    const onExpired = vi.fn();
    setup({ onExpired });

    act(() => {
      vi.advanceTimersByTime(5000);
    });

    expect(mockMutate).toHaveBeenCalledTimes(1);

    act(() => {
      vi.advanceTimersByTime(5000);
    });

    expect(mockMutate).toHaveBeenCalledTimes(1);
  });
});

describe('UndoToast timed-status behavior (IS-GAP-030)', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    resetSessionDeletionLifecycle();
    (useDeleteSession as ReturnType<typeof vi.fn>).mockReturnValue({
      mutate: mockMutate,
    });
    mockMutate.mockClear();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('exposes a polite live region announcing the pending deletion', () => {
    setup();

    const status = screen.getByRole('status');
    expect(status).toHaveTextContent('Delete session?');
    expect(status).toContainElement(screen.getByText('Undo'));
  });

  it('pauses the destructive countdown while hovered and resumes from the remainder', () => {
    const onUndo = vi.fn();
    render(
      <UndoToast
        item={{ id: 'toast-1', sessionId: 'sess-123', message: 'Delete session?' }}
        onUndo={onUndo}
        onDeleteStarted={vi.fn(() => true)}
        onDeleteFailed={vi.fn()}
        onExpired={vi.fn()}
      />
    );
    const toast = screen.getByTestId('undo-toast-toast-1');

    act(() => {
      vi.advanceTimersByTime(2000);
    });
    fireEvent.mouseEnter(toast);
    act(() => {
      vi.advanceTimersByTime(10000);
    });
    expect(mockMutate).not.toHaveBeenCalled();

    fireEvent.mouseLeave(toast);
    act(() => {
      vi.advanceTimersByTime(2500);
    });
    expect(mockMutate).not.toHaveBeenCalled();

    act(() => {
      vi.advanceTimersByTime(600);
    });
    expect(mockMutate).toHaveBeenCalledTimes(1);
  });

  it('pauses while keyboard focus is inside and resumes on blur', () => {
    setup();
    const toast = screen.getByTestId('undo-toast-toast-1');
    const undoButton = screen.getByText('Undo');

    act(() => {
      vi.advanceTimersByTime(3000);
    });
    undoButton.focus();
    fireEvent.focus(toast);
    act(() => {
      vi.advanceTimersByTime(10000);
    });
    expect(mockMutate).not.toHaveBeenCalled();

    fireEvent.blur(toast);
    act(() => {
      vi.advanceTimersByTime(2100);
    });
    expect(mockMutate).toHaveBeenCalledTimes(1);
  });

  it('cleans up all timers on unmount so DELETE never fires', () => {
    const { unmount } = setup();

    act(() => {
      vi.advanceTimersByTime(2500);
    });
    unmount();
    act(() => {
      vi.advanceTimersByTime(10000);
    });

    expect(mockMutate).not.toHaveBeenCalled();
  });
});
