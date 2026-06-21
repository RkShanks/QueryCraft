import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QuotaExceededBanner } from './QuotaExceededBanner';

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, params?: Record<string, unknown>) => {
      if (key === 'quota.reset_at' && params && typeof params.time === 'string') {
        return `Resets at: ${params.time}`;
      }
      return key;
    },
    i18n: { language: 'en', changeLanguage: vi.fn() },
  }),
}));

describe('QuotaExceededBanner', () => {
  it('renders localized quota exceeded message', () => {
    render(<QuotaExceededBanner />);
    expect(screen.getByText('error.quota_exceeded')).toBeInTheDocument();
  });

  it('renders reset_at timestamp correctly formatted when provided', () => {
    const mockResetAt = '2026-06-22T00:00:00Z';
    render(<QuotaExceededBanner resetAt={mockResetAt} />);
    const expectedTime = new Date(mockResetAt).toLocaleString();
    expect(screen.getByText(`Resets at: ${expectedTime}`)).toBeInTheDocument();
  });

  it('does not leak internal counter values, policy IDs, or stack traces', () => {
    const mockResetAt = '2026-06-22T00:00:00Z';
    const { container } = render(<QuotaExceededBanner resetAt={mockResetAt} />);
    
    // Check that standard leak patterns do not appear in the text
    const textContent = container.textContent || '';
    expect(textContent).not.toContain('limit');
    expect(textContent).not.toContain('used');
    expect(textContent).not.toContain('policy');
    expect(textContent).not.toContain('role');
    expect(textContent).not.toContain('trace');
  });
});
