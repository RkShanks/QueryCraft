import { createContext, useContext } from 'react';
import type {
  QueryClient,
  UseMutationResult,
  UseQueryResult,
} from '@tanstack/react-query';
import type { getMe, signIn, signOut } from '../api/generated/sdk.gen';
import type { SignInData } from '../api/generated/types.gen';

export type CurrentUserResponse = Awaited<ReturnType<typeof getMe>>;
export type SignInResponse = Awaited<ReturnType<typeof signIn>>;
export type SignOutResponse = Awaited<ReturnType<typeof signOut>>;
export type CurrentUserQuery = Pick<
  UseQueryResult<CurrentUserResponse, Error>,
  'data' | 'isLoading' | 'isFetching' | 'isError' | 'isSuccess' | 'error' | 'refetch'
>;

export interface AuthSessionContextValue {
  authClient: QueryClient;
  currentUserQuery: CurrentUserQuery;
  signInMutation: UseMutationResult<SignInResponse, Error, SignInData['body'], unknown>;
  signOutMutation: UseMutationResult<SignOutResponse, Error, void, unknown>;
}

export const AuthSessionContext = createContext<AuthSessionContextValue | null>(null);

export function useAuthSessionContext(): AuthSessionContextValue | null {
  return useContext(AuthSessionContext);
}
