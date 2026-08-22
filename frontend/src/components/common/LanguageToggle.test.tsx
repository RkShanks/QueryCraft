import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { LanguageToggle } from './LanguageToggle';
import i18n from '../../i18n';

describe('LanguageToggle (IS-GAP-038)', () => {
  beforeEach(async () => {
    window.localStorage.clear();
    await i18n.changeLanguage('en');
  });

  it('renders a compact two-option selector with localized accessible names', () => {
    render(<LanguageToggle />);
    const english = screen.getByRole('button', { name: /english/i });
    const arabic = screen.getByRole('button', { name: /العربية|arabic/i });
    expect(english).toBeInTheDocument();
    expect(arabic).toBeInTheDocument();
    expect(english).toHaveAttribute('aria-pressed', 'true');
    expect(arabic).toHaveAttribute('aria-pressed', 'false');
  });

  it('switches to Arabic and reflects the pressed state', async () => {
    render(<LanguageToggle />);
    fireEvent.click(screen.getByRole('button', { name: /العربية|arabic/i }));
    expect(i18n.language).toMatch(/^ar/);
    await vi.waitFor(() => {
      expect(screen.getByRole('button', { name: /العربية|arabic/i })).toHaveAttribute(
        'aria-pressed',
        'true'
      );
      expect(screen.getByRole('button', { name: /english/i })).toHaveAttribute(
        'aria-pressed',
        'false'
      );
    });
  });

  it('persists the manual choice as a device preference', async () => {
    render(<LanguageToggle />);
    fireEvent.click(screen.getByRole('button', { name: /العربية|arabic/i }));
    await vi.waitFor(() => {
      expect(window.localStorage.getItem('querycraft.language')).toBe('ar');
    });
  });

  it('keeps switching working when localStorage is unavailable (in-memory)', async () => {
    const original = window.localStorage;
    Object.defineProperty(window, 'localStorage', {
      value: {
        getItem: () => {
          throw new DOMException('denied', 'SecurityError');
        },
        setItem: () => {
          throw new DOMException('denied', 'SecurityError');
        },
        removeItem: () => {
          throw new DOMException('denied', 'SecurityError');
        },
        clear: () => undefined,
        key: () => null,
        length: 0,
      },
      writable: true,
      configurable: true,
    });
    try {
      render(<LanguageToggle />);
      fireEvent.click(screen.getByRole('button', { name: /العربية|arabic/i }));
      await vi.waitFor(() => {
        expect(i18n.language).toMatch(/^ar/);
      });
    } finally {
      Object.defineProperty(window, 'localStorage', {
        value: original,
        writable: true,
        configurable: true,
      });
    }
  });
});
