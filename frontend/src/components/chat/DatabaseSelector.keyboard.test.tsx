import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { DatabaseSelector, type UserConnection } from './DatabaseSelector';

const AFTER_SELECTOR_LABEL = 'after selector';
const OTHER_CONTROL_LABEL = 'other';

const connections: UserConnection[] = [
  { id: 'conn-1', display_name: 'Analytics MySQL', database_type: 'mysql' },
  { id: 'conn-2', display_name: 'Production PG', database_type: 'postgresql' },
  { id: 'conn-3', display_name: 'Warehouse MSSQL', database_type: 'mssql' },
];

const openListbox = () => {
  const trigger = screen.getByTestId('database-selector-trigger');
  fireEvent.click(trigger);
  return trigger;
};

const optionEl = (id: string) => screen.getByTestId(`database-selector-option-${id}`);

describe('DatabaseSelector keyboard model (IS-GAP-029)', () => {
  it('exposes a button with listbox popup semantics and aria-controls', () => {
    render(<DatabaseSelector connections={connections} onSelect={vi.fn()} />);
    const trigger = screen.getByTestId('database-selector-trigger');
    expect(trigger).toHaveAttribute('aria-haspopup', 'listbox');
    expect(trigger).toHaveAttribute('aria-expanded', 'false');

    fireEvent.click(trigger);

    expect(trigger).toHaveAttribute('aria-expanded', 'true');
    const listbox = screen.getByRole('listbox', { hidden: false });
    expect(trigger.getAttribute('aria-controls')).toBe(listbox.id);
    screen.getAllByRole('option').forEach((option) => {
      expect(option.tagName).toBe('LI');
      expect(option.querySelectorAll('button')).toHaveLength(0);
    });
  });

  it('focuses the selected option on open', () => {
    render(<DatabaseSelector connections={connections} selectedId="conn-2" onSelect={vi.fn()} />);
    openListbox();
    expect(document.activeElement).toBe(optionEl('conn-2'));
    expect(optionEl('conn-2')).toHaveAttribute('aria-selected', 'true');
  });

  it('focuses the first option on open without a selection', () => {
    render(<DatabaseSelector connections={connections} onSelect={vi.fn()} />);
    openListbox();
    expect(document.activeElement).toBe(optionEl('conn-1'));
  });

  it('moves active focus with ArrowDown/ArrowUp and clamps at the ends', () => {
    render(<DatabaseSelector connections={connections} selectedId="conn-1" onSelect={vi.fn()} />);
    openListbox();

    fireEvent.keyDown(document.activeElement!, { key: 'ArrowDown' });
    expect(document.activeElement).toBe(optionEl('conn-2'));

    fireEvent.keyDown(document.activeElement!, { key: 'ArrowDown' });
    expect(document.activeElement).toBe(optionEl('conn-3'));

    fireEvent.keyDown(document.activeElement!, { key: 'ArrowDown' });
    expect(document.activeElement).toBe(optionEl('conn-3'));

    fireEvent.keyDown(document.activeElement!, { key: 'ArrowUp' });
    expect(document.activeElement).toBe(optionEl('conn-2'));

    fireEvent.keyDown(document.activeElement!, { key: 'ArrowUp' });
    fireEvent.keyDown(document.activeElement!, { key: 'ArrowUp' });
    expect(document.activeElement).toBe(optionEl('conn-1'));
  });

  it('jumps with Home and End', () => {
    render(<DatabaseSelector connections={connections} selectedId="conn-2" onSelect={vi.fn()} />);
    openListbox();

    fireEvent.keyDown(document.activeElement!, { key: 'End' });
    expect(document.activeElement).toBe(optionEl('conn-3'));

    fireEvent.keyDown(document.activeElement!, { key: 'Home' });
    expect(document.activeElement).toBe(optionEl('conn-1'));
  });

  it('selects with Enter and Space, closes, and restores trigger focus', () => {
    const onSelect = vi.fn();
    render(
      <DatabaseSelector connections={connections} selectedId="conn-1" onSelect={onSelect} />
    );
    const trigger = openListbox();

    fireEvent.keyDown(document.activeElement!, { key: 'ArrowDown' });
    fireEvent.keyDown(document.activeElement!, { key: 'Enter' });
    expect(onSelect).toHaveBeenCalledTimes(1);
    expect(onSelect).toHaveBeenCalledWith('conn-2');
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
    expect(document.activeElement).toBe(trigger);

    fireEvent.click(trigger);
    fireEvent.keyDown(document.activeElement!, { key: 'ArrowDown' });
    fireEvent.keyDown(document.activeElement!, { key: ' ' });
    expect(onSelect).toHaveBeenCalledTimes(2);
    expect(onSelect).toHaveBeenLastCalledWith('conn-2');
    expect(document.activeElement).toBe(trigger);
  });

  it('Escape closes without selecting and restores trigger focus', () => {
    const onSelect = vi.fn();
    render(<DatabaseSelector connections={connections} selectedId="conn-1" onSelect={onSelect} />);
    const trigger = openListbox();

    fireEvent.keyDown(document.activeElement!, { key: 'ArrowDown' });
    fireEvent.keyDown(document.activeElement!, { key: 'Escape' });

    expect(onSelect).not.toHaveBeenCalled();
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
    expect(document.activeElement).toBe(trigger);
  });

  it('Tab closes the popup and lets focus continue naturally', () => {
    const focusSpy = vi.spyOn(HTMLElement.prototype, 'focus');
    render(
      <div>
        <DatabaseSelector connections={connections} selectedId="conn-1" onSelect={vi.fn()} />
        <button type="button">{AFTER_SELECTOR_LABEL}</button>
      </div>
    );
    openListbox();
    focusSpy.mockClear();
    fireEvent.keyDown(document.activeElement!, { key: 'Tab' });

    expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
    expect(focusSpy).not.toHaveBeenCalled();
    focusSpy.mockRestore();
  });

  it('typeahead moves active focus by localized prefix match', () => {
    render(<DatabaseSelector connections={connections} selectedId="conn-1" onSelect={vi.fn()} />);
    openListbox();

    fireEvent.keyDown(document.activeElement!, { key: 'p' });
    expect(document.activeElement).toBe(optionEl('conn-2'));

    fireEvent.keyDown(document.activeElement!, { key: 'w' });
    expect(document.activeElement).toBe(optionEl('conn-3'));

    fireEvent.keyDown(document.activeElement!, { key: 'z' });
    expect(document.activeElement).toBe(optionEl('conn-3'));
  });

  it('distinguishes focused option from selected state', () => {
    render(<DatabaseSelector connections={connections} selectedId="conn-1" onSelect={vi.fn()} />);
    openListbox();

    fireEvent.keyDown(document.activeElement!, { key: 'ArrowDown' });
    expect(document.activeElement).toBe(optionEl('conn-2'));
    expect(optionEl('conn-2')).not.toHaveClass('database-selector-item-active');
    expect(optionEl('conn-2')).toHaveAttribute('aria-selected', 'false');
    expect(optionEl('conn-1')).toHaveClass('database-selector-item-active');
    expect(optionEl('conn-1')).toHaveAttribute('aria-selected', 'true');
    expect(optionEl('conn-2')).toHaveClass('database-selector-item-focused');
  });

  it('keeps behavior coherent when the connection list changes while open', () => {
    const { rerender } = render(
      <DatabaseSelector
        connections={connections}
        selectedId="conn-3"
        onSelect={vi.fn()}
      />
    );
    openListbox();
    expect(document.activeElement).toBe(optionEl('conn-3'));

    rerender(
      <DatabaseSelector
        connections={[connections[0], connections[1]]}
        selectedId={null}
        onSelect={vi.fn()}
      />
    );

    const options = screen.queryAllByRole('option');
    expect(options).toHaveLength(2);
    options.forEach((option) => expect(option.getAttribute('aria-selected')).toBe('false'));
    expect(options.some((option) => option === document.activeElement)).toBe(true);
  });

  it('auto-selects a single connection once without stealing focus or duplicating callbacks', () => {
    const onSelect = vi.fn();
    const { rerender } = render(
      <div>
        <DatabaseSelector connections={[connections[0]]} selectedId={null} onSelect={onSelect} />
        <button type="button" data-testid="other">{OTHER_CONTROL_LABEL}</button>
      </div>
    );
    const other = screen.getByTestId('other');
    other.focus();
    expect(document.activeElement).toBe(other);

    rerender(
      <div>
        <DatabaseSelector connections={[{ ...connections[0] }]} selectedId={null} onSelect={onSelect} />
        <button type="button" data-testid="other">{OTHER_CONTROL_LABEL}</button>
      </div>
    );

    expect(onSelect).toHaveBeenCalledTimes(1);
    expect(onSelect).toHaveBeenCalledWith('conn-1');
    expect(document.activeElement).toBe(other);
  });

  it('closes an outside click without changing selection or focus ownership', () => {
    const onSelect = vi.fn();
    render(<DatabaseSelector connections={connections} selectedId="conn-1" onSelect={onSelect} />);
    openListbox();

    fireEvent.mouseDown(document.body);
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
    expect(onSelect).not.toHaveBeenCalled();
  });
});
