import 'whatwg-fetch';
import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { beforeAll, afterEach, afterAll, vi } from 'vitest';
import { server } from './server';
import { resetQueryScenarios } from './handlers';
import { client } from '../api/generated/client.gen';

// MSW (via rettime) registers multiple abort listeners on a shared AbortSignal
// across parallel Vitest workers. The Node.js EventTarget polyfill has a default
// max of 10 listeners, triggering a warning that is not actionable for test setups.
// We suppress only this specific warning rather than silencing all warnings.
// This runs only in the Vitest jsdom environment where process exists.
const g = globalThis as Record<string, unknown>;
if (typeof g.process === 'object' && g.process !== null) {
  const proc = g.process as { emitWarning?: (warning: string | Error, ...rest: unknown[]) => void };
  const _origEmitWarning = proc.emitWarning;
  if (_origEmitWarning) {
    proc.emitWarning = (warning: string | Error, ...rest: unknown[]) => {
      const msg = typeof warning === 'string' ? warning : warning.message;
      if (msg.includes('Possible EventTarget memory leak detected')) {
        return;
      }
      _origEmitWarning(warning, ...rest);
    };
  }
}

beforeAll(() => {
  server.listen({ onUnhandledRequest: 'error' });
  client.setConfig({ baseUrl: 'http://localhost:3000/api/v1' });
});

import en from '../locales/en.json';

const translations: Record<string, string> = en as unknown as Record<string, string>;

const mockT = (key: string, options?: unknown) => {
  if (typeof options === 'string') return options;
  const opts = options as Record<string, unknown> | undefined;
  const defaultValue = opts?.defaultValue as string | undefined;
  const value = translations[key] ?? defaultValue ?? key;
  return value.replace(/\{\{(\w+)\}\}/g, (_, match) => String(opts?.[match] ?? `{{${match}}}`));
};

const mockI18n = {
  changeLanguage: () => Promise.resolve(),
  language: 'en',
};

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: mockT,
    i18n: mockI18n,
  }),
  initReactI18next: {
    type: '3rdParty',
    init: () => {},
  },
}));

afterEach(() => {
  cleanup();
  server.resetHandlers();
  resetQueryScenarios();
});

afterAll(() => server.close());
