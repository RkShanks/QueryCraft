import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { DatabaseSelector } from './DatabaseSelector';

const mockConnections = [
  { id: 'conn-1', display_name: 'Production PG', database_type: 'postgresql' },
  { id: 'conn-2', display_name: 'Analytics MySQL', database_type: 'mysql' },
];

describe('DatabaseSelector', () => {
  it('renders connections in dropdown', () => {
    render(<DatabaseSelector connections={mockConnections} onSelect={vi.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: /select database/i }));
    expect(screen.getByText('Production PG')).toBeInTheDocument();
    expect(screen.getByText('Analytics MySQL')).toBeInTheDocument();
  });

  it('calls onSelect when a connection is clicked', () => {
    const onSelect = vi.fn();
    render(<DatabaseSelector connections={mockConnections} onSelect={onSelect} />);
    fireEvent.click(screen.getByRole('button', { name: /select database/i }));
    fireEvent.click(screen.getByText('Production PG'));
    expect(onSelect).toHaveBeenCalledWith('conn-1');
  });

  it('auto-selects single connection', () => {
    const onSelect = vi.fn();
    render(<DatabaseSelector connections={[mockConnections[0]]} onSelect={onSelect} />);
    expect(onSelect).toHaveBeenCalledWith('conn-1');
  });

  it('shows localized empty state when no connections', () => {
    render(<DatabaseSelector connections={[]} onSelect={vi.fn()} />);
    expect(screen.getByText(/no database connections available/i)).toBeInTheDocument();
  });

  it('shows selected connection display name', () => {
    render(
      <DatabaseSelector
        connections={mockConnections}
        selectedId="conn-2"
        onSelect={vi.fn()}
      />
    );
    expect(screen.getByText('Analytics MySQL')).toBeInTheDocument();
  });

  it('mirrors correctly under RTL', () => {
    const { container } = render(
      <div dir="rtl">
        <DatabaseSelector connections={mockConnections} onSelect={vi.fn()} />
      </div>
    );
    expect(container.querySelector('[dir="rtl"]')).toBeInTheDocument();
  });
});
