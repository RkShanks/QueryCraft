import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { signIn, getMe, signOut, listSsoProviders } from '../api/generated/sdk.gen';
import type { SignInData } from '../api/generated/types.gen';
import { withRequestDeadline } from '../api/requestScope';
import { handleSessionExpiry } from '../auth/sessionExpiry';
import { useAuthSessionContext } from '../auth/AuthSessionContext';
import { CURRENT_USER_QUERY_KEY } from '../providers/QueryProvider';

export const useSignIn = () => {
  const authSession = useAuthSessionContext();
  const queryClient = useQueryClient();
  const fallbackMutation = useMutation({
    mutationFn: (data: SignInData['body']) => signIn({ body: data, throwOnError: true }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['currentUser'] });
    },
  });
  return authSession?.signInMutation ?? fallbackMutation;
};

export const useCurrentUser = () => {
  const authSession = useAuthSessionContext();
  const fallbackQuery = useQuery({
    queryKey: CURRENT_USER_QUERY_KEY,
    queryFn: async ({ signal }) => {
      const sourcePath = window.location.pathname;
      try {
        return await withRequestDeadline(
          (requestSignal) => getMe({ throwOnError: true, signal: requestSignal }),
          { signal },
        );
      } catch (error) {
        handleSessionExpiry(error, sourcePath);
        throw error;
      }
    },
    retry: false,
    enabled: authSession === null,
  }, authSession?.authClient);
  return authSession?.currentUserQuery ?? fallbackQuery;
};

export const useSignOut = () => {
  const authSession = useAuthSessionContext();
  const queryClient = useQueryClient();
  const fallbackMutation = useMutation({
    mutationFn: () => signOut({ throwOnError: true }),
    onSuccess: () => {
      queryClient.clear();
    },
  });
  return authSession?.signOutMutation ?? fallbackMutation;
};

export const useSsoProviders = () => {
  return useQuery({
    queryKey: ['ssoProviders'],
    queryFn: ({ signal }) =>
      withRequestDeadline(
        (requestSignal) => listSsoProviders({ throwOnError: true, signal: requestSignal }),
        { signal },
      ).then((response) => response.data?.providers ?? []),
    retry: false,
  });
};

// Optional composite hook
export const useAuth = () => {
  const { data: userResponse, isLoading, isError } = useCurrentUser();
  const signInMutation = useSignIn();
  const signOutMutation = useSignOut();

  return {
    user: isError ? null : userResponse?.data ?? null,
    isLoading,
    signIn: signInMutation.mutateAsync,
    signOut: signOutMutation.mutateAsync,
    isAuthenticated: !!(userResponse?.data && !isError),
  };
};
