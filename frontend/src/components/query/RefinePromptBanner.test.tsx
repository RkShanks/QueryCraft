import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { RefinePromptBanner } from './RefinePromptBanner';
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

describe('RefinePromptBanner', () => {
  beforeEach(() => {
    mockT.mockClear();
  });

  it('renders heading and body for max_retries reason with role alert', () => {
    render(
      <RefinePromptBanner
        refinePrompt={{ reason: 'max_retries' }}
        onRefine={vi.fn()}
      />,
      { wrapper: createWrapper() }
    );

    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.getByText('query.refine.heading')).toBeInTheDocument();
    expect(screen.getByText('query.refine.body.maxRetries')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'query.refine.cta' })).toBeInTheDocument();

    expect(mockT).toHaveBeenCalledWith('query.refine.heading');
    expect(mockT).toHaveBeenCalledWith('query.refine.body.maxRetries');
    expect(mockT).toHaveBeenCalledWith('query.refine.cta');
  });

  it('renders body for byte_equal_duplicate reason', () => {
    render(
      <RefinePromptBanner
        refinePrompt={{ reason: 'byte_equal_duplicate' }}
        onRefine={vi.fn()}
      />,
      { wrapper: createWrapper() }
    );

    expect(screen.getByText('query.refine.body.byteEqual')).toBeInTheDocument();
    expect(mockT).toHaveBeenCalledWith('query.refine.body.byteEqual');
  });

  it('renders body for evaluator_blocked reason', () => {
    render(
      <RefinePromptBanner
        refinePrompt={{ reason: 'evaluator_blocked' }}
        onRefine={vi.fn()}
      />,
      { wrapper: createWrapper() }
    );

    expect(screen.getByText('query.refine.body.evaluatorBlocked')).toBeInTheDocument();
    expect(mockT).toHaveBeenCalledWith('query.refine.body.evaluatorBlocked');
  });

  it('calls onRefine when CTA is clicked', () => {
    const onRefine = vi.fn();
    render(
      <RefinePromptBanner
        refinePrompt={{ reason: 'max_retries' }}
        onRefine={onRefine}
      />,
      { wrapper: createWrapper() }
    );

    fireEvent.click(screen.getByRole('button', { name: 'query.refine.cta' }));
    expect(onRefine).toHaveBeenCalledTimes(1);
  });
});
