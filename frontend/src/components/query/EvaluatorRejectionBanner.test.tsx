import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { EvaluatorRejectionBanner } from './EvaluatorRejectionBanner';
import { createWrapper } from '../../test/utils';

const mockT = vi.fn((key: string, options?: unknown) => {
  if (typeof options === 'string') return options;
  const opts = options as { defaultValue?: string; reason?: string } | undefined;
  if (opts?.reason) return `${key} (reason: ${opts.reason})`;
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

  it('renders heading, reason, failed rule, and violations with role alert', () => {
    render(
      <EvaluatorRejectionBanner
        evaluatorRejection={{
          failedRule: 'ReadOnlyRule',
          reason: 'SQL contains UPDATE statement',
          violations: ['Data modifying statement detected', 'Unsafe pattern pg_sleep'],
        }}
      />,
      { wrapper: createWrapper() }
    );

    const alert = screen.getByRole('alert');
    expect(alert).toBeInTheDocument();

    expect(screen.getByText('query.evaluatorRejection.heading')).toBeInTheDocument();
    expect(screen.getByText(/reason: SQL contains UPDATE statement/i)).toBeInTheDocument();
    expect(screen.getByText('query.evaluatorRejection.rule.ReadOnlyRule')).toBeInTheDocument();

    expect(screen.getByText('Data modifying statement detected')).toBeInTheDocument();
    expect(screen.getByText('Unsafe pattern pg_sleep')).toBeInTheDocument();

    expect(mockT).toHaveBeenCalledWith('query.evaluatorRejection.heading');
    expect(mockT).toHaveBeenCalledWith(
      'query.evaluatorRejection.body',
      expect.objectContaining({ reason: 'SQL contains UPDATE statement' })
    );
    expect(mockT).toHaveBeenCalledWith('query.evaluatorRejection.rule.ReadOnlyRule');
  });

  it('renders without violations array', () => {
    render(
      <EvaluatorRejectionBanner
        evaluatorRejection={{
          failedRule: 'SchemaValidationRule',
          reason: 'Unknown table referenced',
        }}
      />,
      { wrapper: createWrapper() }
    );

    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.getByText('query.evaluatorRejection.heading')).toBeInTheDocument();
    expect(screen.queryByRole('list')).not.toBeInTheDocument();
  });
});
