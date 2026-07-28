import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { signIn, getMe, signOut, listSsoProviders } from '../api/generated/sdk.gen';
import type { SignInData } from '../api/generated/types.gen';
import { handleSessionExpiry } from '../auth/sessionExpiry';

export const useSignIn = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: SignInData['body']) => signIn({ body: data, throwOnError: true }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['currentUser'] });
    },
  });
};

export const useCurrentUser = () => {
  return useQuery({
    queryKey: ['currentUser'],
    queryFn: async () => {
      const sourcePath = window.location.pathname;
      try {
        return await getMe({ throwOnError: true });
      } catch (error) {
        handleSessionExpiry(error, sourcePath);
        throw error;
      }
    },
    retry: false,
  });
};

export const useSignOut = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => signOut({ throwOnError: true }),
    onSuccess: () => {
      queryClient.clear();
    },
  });
};

export const useSsoProviders = () => {
  return useQuery({
    queryKey: ['ssoProviders'],
    queryFn: async () => {
      const response = await listSsoProviders({ throwOnError: true });
      return response.data?.providers ?? [];
    },
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
