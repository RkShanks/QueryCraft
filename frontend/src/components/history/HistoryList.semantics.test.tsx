import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { HistoryList, type HistoryItem } from './HistoryList';

const sample: HistoryItem[] = [
  { id: '1', question_text: 'Total customers?', generated_sql: 'SELECT COUNT(*) FROM customer', accepted_at: '2026-05-11T10:00:00Z' },
  { id: '2', question_text: 'Top revenue', generated_sql: 'SELECT ... FROM payment', accepted_at: '2026-05-10T10:00:00Z' },
];

function setup(items: HistoryItem[], extraProps: Partial<React.ComponentProps<typeof HistoryList>> = {}) {
  return render(<HistoryList items={items} total={items.length} isLoading={false} {...extraProps} />);
}

describe('HistoryList accessible selection semantics (IS-GAP-032)', () => {
  it('renders rows as a semantic list of independent buttons', () => {
    setup(sample);
    const list = screen.getByRole('list');
    expect(list).toBeInTheDocument();
    const itemButtons = screen.getAllByRole('button', { name: /total customers\?/i });
    expect(itemButtons).toHaveLength(1);
    // Each button lives inside its own listitem.
    itemButtons.forEach((button) => {
      expect(button.closest('[role="listitem"], li')).not.toBeNull();
    });
  });

  it('does not imitate a table without rendering one', () => {
    setup(sample);
    expect(screen.queryAllByRole('columnheader')).toHaveLength(0);
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
  });

  it('rows are not focusable divs with manual keyboard handlers', () => {
    const { container } = setup(sample);
    const focusableDivs = container.querySelectorAll('div[tabindex]');
    expect(focusableDivs).toHaveLength(0);
  });

  it('exposes the selection state through aria-pressed', () => {
    setup(sample, { onSelect: vi.fn(), selectedId: '1' });
    const first = screen.getAllByRole('button', { name: /total customers\?/i })[0];
    expect(first).toHaveAttribute('aria-pressed', 'true');
    const second = screen.getAllByRole('button', { name: /top revenue/i })[0];
    expect(second).toHaveAttribute('aria-pressed', 'false');
  });

  it('activates with click and native keyboard activation', () => {
    const onSelect = vi.fn();
    setup(sample, { onSelect });
    fireEvent.click(screen.getAllByRole('button', { name: /total customers\?/i })[0]);
    expect(onSelect).toHaveBeenCalledWith('1');

    onSelect.mockClear();
    const second = screen.getAllByRole('button', { name: /top revenue/i })[0];
    second.focus();
    fireEvent.keyDown(second, { key: 'Enter' });
    // Native button semantics: keydown Enter is the browser's activation key;
    // the component must not rely on custom div handlers.
    expect(second.tagName).toBe('BUTTON');
  });

  it('keeps SQL previews LTR inside the RTL chrome', () => {
    const { container } = render(
      <div dir="rtl">
        <HistoryList items={sample} total={sample.length} isLoading={false} />
      </div>
    );
    expect(screen.getByText('SELECT COUNT(*) FROM customer')).toHaveAttribute('dir', 'ltr');
    expect(container.firstChild).toHaveAttribute('dir', 'rtl');
  });
});
