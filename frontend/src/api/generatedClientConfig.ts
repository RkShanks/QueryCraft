import type { CreateClientConfig } from './generated/client.gen';
import { validatedApiFetch } from './responseValidation';

export const createClientConfig: CreateClientConfig = (config) => ({
  ...config,
  credentials: 'include',
  fetch: validatedApiFetch,
});
