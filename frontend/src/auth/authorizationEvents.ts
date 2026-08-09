type SessionExpiryListener = () => void;

const sessionExpiryListeners = new Set<SessionExpiryListener>();

export function notifySessionExpiry(): void {
  sessionExpiryListeners.forEach((listener) => listener());
}

export function subscribeToSessionExpiry(listener: SessionExpiryListener): () => void {
  sessionExpiryListeners.add(listener);
  return () => sessionExpiryListeners.delete(listener);
}
