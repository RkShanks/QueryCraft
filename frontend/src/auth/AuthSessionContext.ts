import { createContext, useContext } from 'react';
import type {
  QueryClient,
  UseMutationResult,
  UseQueryResult,
} from '@tanstack/react-query';
import type { getMe, signOut } from '../api/generated/sdk.gen';

export type CurrentUserResponse = Awaited<ReturnType<typeof getMe>>;
export type SignOutResponse = Awaited<ReturnType<typeof signOut>>;

export interface AuthSessionContextValue {
  authClient: QueryClient;
  currentUserQuery: UseQueryResult<CurrentUserResponse, Error>;
  signOutMutation: UseMutationResult<SignOutResponse, Error, void, unknown>;
}

export const AuthSessionContext = createContext<AuthSessionContextValue | null>(null);

export function useAuthSessionContext(): AuthSessionContextValue | null {
  return useContext(AuthSessionContext);
}
