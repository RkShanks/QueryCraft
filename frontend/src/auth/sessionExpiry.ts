type ApiError = {
  status?: number;
  response?: { status?: number };
  error?: string;
  message_key?: string;
};

export function isSessionExpiryError(error: unknown): boolean {
  const apiError = error as ApiError | undefined;
  const isUnauthorizedPayload =
    apiError?.error === 'unauthorized' && apiError.message_key === 'error.unauthorized';
  return apiError?.status === 401 || apiError?.response?.status === 401 || isUnauthorizedPayload;
}

export function isPermissionDeniedError(error: unknown): boolean {
  const apiError = error as ApiError | undefined;
  return apiError?.status === 403 || apiError?.response?.status === 403;
}

export function handleSessionExpiry(error: unknown, sourcePath = window.location.pathname) {
  const isUnauthorized = isSessionExpiryError(error);
  if (!isUnauthorized || sourcePath === '/sign-in') return;

  window.history.replaceState({}, '', '/sign-in?error=session_expired');
  window.dispatchEvent(new PopStateEvent('popstate'));
}
