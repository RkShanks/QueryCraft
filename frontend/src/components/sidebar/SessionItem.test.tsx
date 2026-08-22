import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { SessionItem } from './SessionItem';

const session = {
  id: 'sess-1',
  preview_text: 'Quarterly revenue breakdown',
  created_at: '2026-08-01T10:00:00Z',
  last_activity_at: '2026-08-20T10:00:00Z',
};

describe('SessionItem interaction accessibility (IS-GAP-030)', () => {
  it('exposes activation as a dedicated control without nested interactive elements', () => {
    render(
      <SessionItem
        session={session}
        isActive={false}
        onClick={vi.fn()}
        onDelete={vi.fn()}
      />
    );

    const container = screen.getByTestId('session-item-sess-1');
    expect(container).not.toHaveAttribute('role', 'button');
    expect(container).not.toHaveAttribute('tabindex');

    const main = screen.getByTestId('session-item-main-sess-1');
    expect(main.tagName).toBe('BUTTON');
    expect(main.querySelector('button')).toBeNull();
    expect(main).toHaveAccessibleName('Quarterly revenue breakdown');

    const del = screen.getByTestId('session-delete-sess-1');
    expect(del.tagName).toBe('BUTTON');
    expect(main.contains(del)).toBe(false);
    expect(del).toHaveAccessibleName('Delete');
  });

  it('activates only through its own control', () => {
    const onClick = vi.fn();
    render(
      <SessionItem
        session={session}
        isActive={false}
        onClick={onClick}
        onDelete={vi.fn()}
      />
    );

    fireEvent.click(screen.getByTestId('session-item-main-sess-1'));
    expect(onClick).toHaveBeenCalledTimes(1);

    fireEvent.keyDown(screen.getByTestId('session-item-main-sess-1'), { key: 'Enter' });
    expect(onClick).toHaveBeenCalledTimes(2);
  });

  it('delete stops propagation so the session is not activated', () => {
    const onClick = vi.fn();
    const onDelete = vi.fn();
    render(
      <SessionItem
        session={session}
        isActive={false}
        onClick={onClick}
        onDelete={onDelete}
      />
    );

    fireEvent.click(screen.getByTestId('session-delete-sess-1'));
    expect(onDelete).toHaveBeenCalledTimes(1);
    expect(onClick).not.toHaveBeenCalled();
  });

  it('renders one focusable localized control in collapsed mode', () => {
    render(
      <SessionItem
        session={session}
        isActive={false}
        onClick={vi.fn()}
        onDelete={vi.fn()}
        collapsed
      />
    );

    const container = screen.getByTestId('session-item-sess-1');
    expect(container.querySelectorAll('button')).toHaveLength(1);
    const collapsedControl = screen.getByTestId('session-item-main-sess-1');
    expect(collapsedControl.tagName).toBe('BUTTON');
    expect(collapsedControl).toHaveAccessibleName('Quarterly revenue breakdown');
  });
});
