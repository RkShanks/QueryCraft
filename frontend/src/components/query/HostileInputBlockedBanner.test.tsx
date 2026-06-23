import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { HostileInputBlockedBanner } from './HostileInputBlockedBanner';

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    i18n: { language: 'en', changeLanguage: vi.fn() },
  }),
}));

describe('HostileInputBlockedBanner', () => {
  it('renders localized hostile input blocked message', () => {
    render(<HostileInputBlockedBanner />);
    expect(screen.getByText('error.hostile_input_blocked')).toBeInTheDocument();
  });

  it('does not leak security details (rule names, confidence, patterns, stack traces)', () => {
    const { container } = render(<HostileInputBlockedBanner />);
    
    const textContent = container.textContent || '';
    expect(textContent).not.toContain('rule');
    expect(textContent).not.toContain('confidence');
    expect(textContent).not.toContain('pattern');
    expect(textContent).not.toContain('category');
    expect(textContent).not.toContain('payload');
    expect(textContent).not.toContain('trace');
  });
});
