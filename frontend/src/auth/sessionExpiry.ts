type ApiError = {
  status?: number;
  response?: { status?: number };
  error?: string;
  message_key?: string;
};

export function handleSessionExpiry(error: unknown, sourcePath = window.location.pathname) {
  const apiError = error as ApiError | undefined;
  const isUnauthorizedPayload =
    apiError?.error === 'unauthorized' && apiError.message_key === 'error.unauthorized';
  const isUnauthorized =
    apiError?.status === 401 || apiError?.response?.status === 401 || isUnauthorizedPayload;
  if (!isUnauthorized || sourcePath === '/sign-in') return;

  window.history.replaceState({}, '', '/sign-in?error=session_expired');
  window.dispatchEvent(new PopStateEvent('popstate'));
}
