import 'whatwg-fetch';
import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { beforeAll, afterEach, afterAll } from 'vitest';
import { server } from './server';
import { client } from '../api/generated/client.gen';

beforeAll(() => {
  server.listen({ onUnhandledRequest: 'error' });
  client.setConfig({ baseUrl: 'http://localhost:3000/api/v1' }); 
});

afterEach(() => {
  cleanup();
  server.resetHandlers();
});

afterAll(() => server.close());
