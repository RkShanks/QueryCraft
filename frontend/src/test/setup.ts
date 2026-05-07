import 'whatwg-fetch';
import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { beforeAll, afterEach, afterAll, vi } from 'vitest';
import { server } from './server';
import { resetQueryScenarios } from './handlers';
import { client } from '../api/generated/client.gen';

beforeAll(() => {
  server.listen({ onUnhandledRequest: 'error' });
  client.setConfig({ baseUrl: 'http://localhost:3000/api/v1' }); 
});

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, options?: unknown) => {
      if (typeof options === 'string') return options;
      const opts = options as Record<string, unknown> | undefined;
      const defaultValue = opts?.defaultValue as string | undefined;
      const value = defaultValue || key;
      return value.replace(/\{\{(\w+)\}\}/g, (_, match) => String(opts?.[match] ?? `{{${match}}}`));
    },
    i18n: {
      changeLanguage: () => Promise.resolve(),
    },
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
