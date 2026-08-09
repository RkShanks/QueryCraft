type SessionExpiryListener = () => void;
type PermissionDeniedListener = () => void;

const sessionExpiryListeners = new Set<SessionExpiryListener>();
const permissionDeniedListeners = new Set<PermissionDeniedListener>();

export function notifySessionExpiry(): void {
  sessionExpiryListeners.forEach((listener) => listener());
}

export function subscribeToSessionExpiry(listener: SessionExpiryListener): () => void {
  sessionExpiryListeners.add(listener);
  return () => sessionExpiryListeners.delete(listener);
}

export function notifyPermissionDenied(): void {
  permissionDeniedListeners.forEach((listener) => listener());
}

export function subscribeToPermissionDenied(listener: PermissionDeniedListener): () => void {
  permissionDeniedListeners.add(listener);
  return () => permissionDeniedListeners.delete(listener);
}
