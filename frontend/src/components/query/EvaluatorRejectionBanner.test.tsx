import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { EvaluatorRejectionBanner } from './EvaluatorRejectionBanner';
import { createWrapper } from '../../test/utils';

const mockT = vi.fn((key: string, options?: unknown) => {
  if (typeof options === 'string') return options;
  const opts = options as Record<string, unknown> | undefined;
  if (opts && Object.keys(opts).length > 0) {
    const entries = Object.entries(opts)
      .filter(([k]) => k !== 'defaultValue')
      .map(([k, v]) => `${k}=${v}`)
      .join(', ');
    return entries ? `${key} (${entries})` : key;
  }
  return opts?.defaultValue || key;
});

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: mockT,
    i18n: { changeLanguage: () => Promise.resolve() },
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}));

describe('EvaluatorRejectionBanner', () => {
  beforeEach(() => {
    mockT.mockClear();
  });

  it('renders heading with role alert', () => {
    render(
      <EvaluatorRejectionBanner violations={[{ type: 'read_only' }]} />,
      { wrapper: createWrapper() }
    );

    const alert = screen.getByRole('alert');
    expect(alert).toBeInTheDocument();
    expect(screen.getByText('query.evaluatorRejection.heading')).toBeInTheDocument();
  });

  it('renders read_only-specific message + i18n key query.evaluator.read_only', () => {
    render(
      <EvaluatorRejectionBanner violations={[{ type: 'read_only' }]} />,
      { wrapper: createWrapper() }
    );

    expect(screen.getByText('query.evaluator.read_only')).toBeInTheDocument();
    expect(mockT).toHaveBeenCalledWith('query.evaluator.read_only', undefined);
  });

  it('renders schema_validation-specific message + structured detail (unknown identifier)', () => {
    render(
      <EvaluatorRejectionBanner violations={[{ type: 'schema_validation', detail: 'users' }]} />,
      { wrapper: createWrapper() }
    );

    expect(screen.getByText('query.evaluator.schema_validation (identifier=users)')).toBeInTheDocument();
    expect(mockT).toHaveBeenCalledWith('query.evaluator.schema_validation', { identifier: 'users' });
  });

  it('renders single_statement-specific message', () => {
    render(
      <EvaluatorRejectionBanner violations={[{ type: 'single_statement' }]} />,
      { wrapper: createWrapper() }
    );

    expect(screen.getByText('query.evaluator.single_statement')).toBeInTheDocument();
    expect(mockT).toHaveBeenCalledWith('query.evaluator.single_statement', undefined);
  });

  it('renders unsafe_pattern-specific message + structured detail (pattern name)', () => {
    render(
      <EvaluatorRejectionBanner violations={[{ type: 'unsafe_pattern', detail: 'pg_sleep' }]} />,
      { wrapper: createWrapper() }
    );

    expect(screen.getByText('query.evaluator.unsafe_pattern (pattern=pg_sleep)')).toBeInTheDocument();
    expect(mockT).toHaveBeenCalledWith('query.evaluator.unsafe_pattern', { pattern: 'pg_sleep' });
  });

  it('renders syntax-specific message', () => {
    render(
      <EvaluatorRejectionBanner violations={[{ type: 'syntax', detail: 'Unexpected token' }]} />,
      { wrapper: createWrapper() }
    );

    expect(screen.getByText('query.evaluator.syntax (details=Unexpected token)')).toBeInTheDocument();
    expect(mockT).toHaveBeenCalledWith('query.evaluator.syntax', { details: 'Unexpected token' });
  });

  it('renders multiple violations ordered by index', () => {
    render(
      <EvaluatorRejectionBanner
        violations={[
          { type: 'read_only' },
          { type: 'schema_validation', detail: 'orders' },
          { type: 'unsafe_pattern', detail: 'pg_sleep' },
        ]}
      />,
      { wrapper: createWrapper() }
    );

    const items = screen.getAllByRole('listitem');
    expect(items).toHaveLength(3);
    expect(items[0]).toHaveTextContent('query.evaluator.read_only');
    expect(items[1]).toHaveTextContent('query.evaluator.schema_validation (identifier=orders)');
    expect(items[2]).toHaveTextContent('query.evaluator.unsafe_pattern (pattern=pg_sleep)');
  });

  it('falls back to generic key query.evaluator.unknown for unrecognized type', () => {
    render(
      <EvaluatorRejectionBanner violations={[{ type: 'custom_rule_xyz' }]} />,
      { wrapper: createWrapper() }
    );

    expect(screen.getByText('query.evaluator.unknown')).toBeInTheDocument();
    expect(mockT).toHaveBeenCalledWith('query.evaluator.unknown', undefined);
  });

  it('does not crash with empty violations array', () => {
    render(
      <EvaluatorRejectionBanner violations={[]} />,
      { wrapper: createWrapper() }
    );

    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.queryByRole('listitem')).not.toBeInTheDocument();
  });
});
