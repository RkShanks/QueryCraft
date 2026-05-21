import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ConnectionErrorCard } from '../components/chat/ConnectionErrorCard';
import { PromptInput } from '../components/chat/PromptInput';

describe('Wave 14 i18n / RTL / a11y sweep', () => {
  describe('ConnectionErrorCard a11y', () => {
    it('action button has accessible name matching translated text', () => {
      render(<ConnectionErrorCard kind="noConnections" />);
      const btn = screen.getByRole('button');
      expect(btn).toHaveAccessibleName(/add connection/i);
    });

    it('renders all known error kinds with localized text', () => {
      const kinds = [
        'noConnections',
        'disabled',
        'unhealthy',
        'noSchema',
        'queryExecutionFailed',
      ] as const;
      kinds.forEach((kind) => {
        const { unmount } = render(<ConnectionErrorCard kind={kind} />);
        expect(screen.getByRole('alert')).toBeInTheDocument();
        unmount();
      });
    });
  });

  describe('PromptInput a11y', () => {
    it('warning banner has role=alert and aria-live', () => {
      render(
        <PromptInput
          onSubmit={() => {}}
          connections={[]}
          selectedConnectionId={null}
          onSelectConnection={() => {}}
        />
      );
      const warning = screen.getByTestId('prompt-input-warning');
      expect(warning).toHaveAttribute('role', 'alert');
      expect(warning).toHaveAttribute('aria-live', 'polite');
    });
  });

  describe('Locale key parity', () => {
    it('all Wave 14 selector and error keys exist in en', async () => {
      const en = (await import('../locales/en.json')).default;
      expect(en).toHaveProperty('databaseSelector.selectDatabase');
      expect(en).toHaveProperty('databaseSelector.empty');
      expect(en).toHaveProperty('error.noConnections.title');
      expect(en).toHaveProperty('error.disabled.title');
      expect(en).toHaveProperty('error.unhealthy.title');
      expect(en).toHaveProperty('error.noSchema.title');
      expect(en).toHaveProperty('error.queryExecutionFailed.title');
    });

    it('all Wave 14 selector and error keys exist in ar', async () => {
      const ar = (await import('../locales/ar.json')).default;
      expect(ar).toHaveProperty('databaseSelector.selectDatabase');
      expect(ar).toHaveProperty('databaseSelector.empty');
      expect(ar).toHaveProperty('error.noConnections.title');
      expect(ar).toHaveProperty('error.disabled.title');
      expect(ar).toHaveProperty('error.unhealthy.title');
      expect(ar).toHaveProperty('error.noSchema.title');
      expect(ar).toHaveProperty('error.queryExecutionFailed.title');
    });
  });
});
