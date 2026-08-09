import { createContext, useContext } from 'react';
import type { QueryClient, UseQueryResult } from '@tanstack/react-query';
import type { getMe } from '../api/generated/sdk.gen';

export type CurrentUserResponse = Awaited<ReturnType<typeof getMe>>;

export interface AuthSessionContextValue {
  authClient: QueryClient;
  currentUserQuery: UseQueryResult<CurrentUserResponse, Error>;
}

export const AuthSessionContext = createContext<AuthSessionContextValue | null>(null);

export function useAuthSessionContext(): AuthSessionContextValue | null {
  return useContext(AuthSessionContext);
}
