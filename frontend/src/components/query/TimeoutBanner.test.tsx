import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { TimeoutBanner } from './TimeoutBanner';
import { createWrapper } from '../../test/utils';

const mockT = vi.fn((key: string, options?: unknown) => {
  if (typeof options === 'string') return options;
  const opts = options as { defaultValue?: string } | undefined;
  return opts?.defaultValue || key;
});

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: mockT,
    i18n: { changeLanguage: () => Promise.resolve() },
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}));

describe('TimeoutBanner', () => {
  beforeEach(() => {
    mockT.mockClear();
  });

  it('renders heading, body, and retry CTA with role alert', () => {
    render(
      <TimeoutBanner timeout onRetry={vi.fn()} />,
      { wrapper: createWrapper() }
    );

    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.getByText('query.timeout.heading')).toBeInTheDocument();
    expect(screen.getByText('query.timeout.body')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'query.timeout.cta' })).toBeInTheDocument();

    expect(mockT).toHaveBeenCalledWith('query.timeout.heading');
    expect(mockT).toHaveBeenCalledWith('query.timeout.body');
    expect(mockT).toHaveBeenCalledWith('query.timeout.cta');
  });

  it('calls onRetry when CTA is clicked', () => {
    const onRetry = vi.fn();
    render(
      <TimeoutBanner timeout onRetry={onRetry} />,
      { wrapper: createWrapper() }
    );

    fireEvent.click(screen.getByRole('button', { name: 'query.timeout.cta' }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });
});
