import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import React from 'react';
import en from '../../src/locales/en.json';

// Override global mock with real translations + missing-key throw
function getTranslationValue(obj: Record<string, unknown>, key: string): string | undefined {
  const val = obj[key];
  return typeof val === 'string' ? val : undefined;
}

function flattenKeys(obj: Record<string, unknown>, prefix = ''): string[] {
  return Object.entries(obj).flatMap(([k, v]) => {
    const key = prefix ? `${prefix}.${k}` : k;
    if (v && typeof v === 'object' && !Array.isArray(v)) {
      return flattenKeys(v as Record<string, unknown>, key);
    }
    return [key];
  });
}

const allKeys = flattenKeys(en);
const keySet = new Set(allKeys);

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, options?: unknown) => {
      if (!keySet.has(key)) {
        throw new Error(`Missing i18n key: ${key}`);
      }
      const val = getTranslationValue(en, key);
      if (typeof val !== 'string') {
        throw new Error(`i18n key ${key} is not a string`);
      }
      const opts = (options as Record<string, unknown> | undefined) || {};
      return val.replace(/\{\{(\w+)\}\}/g, (_, match) => String(opts[match] ?? `{{${match}}}`));
    },
    i18n: { changeLanguage: () => Promise.resolve() },
  }),
  I18nextProvider: ({ children }: { children: React.ReactNode }) => children,
  initReactI18next: { type: '3rdParty' as const, init: () => {} },
}));

function createWrapper() {
  const testQueryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: React.ReactNode }) => (
    <MemoryRouter>
      <QueryClientProvider client={testQueryClient}>{children}</QueryClientProvider>
    </MemoryRouter>
  );
}

// Helper: scan DOM for raw key pattern
function findRawKeys(container: HTMLElement): string[] {
  const pattern = /^[a-z][a-zA-Z0-9_]*(\.[a-z][a-zA-Z0-9_]*)+$/;
  const results: string[] = [];
  const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
  let node: Node | null;
  while ((node = walker.nextNode()) !== null) {
    const text = node.textContent?.trim() ?? '';
    if (text && pattern.test(text)) {
      results.push(text);
    }
  }
  return results;
}

describe('T-183: en.json renders without missing-key placeholders', () => {
  it('SignInPage has no raw key strings', async () => {
    const { SignInPage } = await import('../../src/pages/SignInPage');
    const { container } = render(<SignInPage />, { wrapper: createWrapper() });
    const rawKeys = findRawKeys(container);
    expect(rawKeys).toEqual([]);
  });

  it('AskQuestionPage has no raw key strings', async () => {
    const { AskQuestionPage } = await import('../../src/pages/AskQuestionPage');
    const { container } = render(<AskQuestionPage />, { wrapper: createWrapper() });
    const rawKeys = findRawKeys(container);
    expect(rawKeys).toEqual([]);
  });

  it('HistoryPage has no raw key strings', async () => {
    const { default: HistoryPage } = await import('../../src/pages/HistoryPage');
    const { container } = render(<HistoryPage />, { wrapper: createWrapper() });
    const rawKeys = findRawKeys(container);
    expect(rawKeys).toEqual([]);
  });
});
