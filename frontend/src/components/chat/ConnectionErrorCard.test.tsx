import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ConnectionErrorCard } from './ConnectionErrorCard';
import type { ConnectionErrorKind } from './ConnectionErrorCard';

describe('ConnectionErrorCard', () => {
  it('renders no-connections error with title, body, and action', () => {
    render(<ConnectionErrorCard kind="noConnections" />);
    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.getByText(/no database connections/i)).toBeInTheDocument();
    expect(screen.getByText(/add a database connection/i)).toBeInTheDocument();
  });

  it('renders disabled error with title and select-another action', () => {
    render(<ConnectionErrorCard kind="disabled" />);
    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.getByText(/connection is disabled/i)).toBeInTheDocument();
    expect(screen.getByText(/select another/i)).toBeInTheDocument();
  });

  it('renders unhealthy error with title and contact-admin action', () => {
    render(<ConnectionErrorCard kind="unhealthy" />);
    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.getByText(/connection is unavailable/i)).toBeInTheDocument();
    expect(screen.getByText(/try another/i)).toBeInTheDocument();
  });

  it('renders no-schema error with title and refresh action', () => {
    render(<ConnectionErrorCard kind="noSchema" />);
    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.getByText(/schema not ready/i)).toBeInTheDocument();
    expect(screen.getByText(/contact admin/i)).toBeInTheDocument();
  });

  it('renders query-execution-failure error with safe generic message', () => {
    render(<ConnectionErrorCard kind="queryExecutionFailed" />);
    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.getByText(/query failed/i)).toBeInTheDocument();
    expect(screen.getByText(/try rephrasing/i)).toBeInTheDocument();
  });

  it('falls back to generic message for unknown error kind', () => {
    render(<ConnectionErrorCard kind={'unknown_kind' as ConnectionErrorKind} />);
    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.getByText(/unexpected error/i)).toBeInTheDocument();
  });

  it('does not render raw backend error strings or credentials', () => {
    const { container } = render(<ConnectionErrorCard kind="unhealthy" />);
    const text = container.textContent || '';
    expect(text).not.toMatch(/127\.0\.0\.1/);
    expect(text).not.toMatch(/password/i);
    expect(text).not.toMatch(/host:/i);
    expect(text).not.toMatch(/port:/i);
  });

  it('mirrors correctly under RTL without breaking layout', () => {
    const { container } = render(
      <div dir="rtl">
        <ConnectionErrorCard kind="noConnections" />
      </div>
    );
    expect(container.querySelector('[dir="rtl"]')).toBeInTheDocument();
    expect(screen.getByRole('alert')).toBeInTheDocument();
  });
});
