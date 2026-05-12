import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { UndoToast } from '../UndoToast';

vi.mock('../../../hooks/useSessions', () => ({
  useDeleteSession: vi.fn(),
}));

import { useDeleteSession } from '../../../hooks/useSessions';

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
      onExpired={vi.fn()}
      {...props}
    />
  );
}

describe('UndoToast', () => {
  beforeEach(() => {
    vi.useFakeTimers();
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

  it('fires DELETE after 5 seconds', () => {
    const onExpired = vi.fn();
    setup({ onExpired });

    expect(mockMutate).not.toHaveBeenCalled();

    act(() => {
      vi.advanceTimersByTime(5000);
    });

    expect(mockMutate).toHaveBeenCalledWith('sess-123');
    expect(onExpired).toHaveBeenCalled();
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
