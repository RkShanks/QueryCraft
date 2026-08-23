const deletionVersions = new Map<string, number>();
const unavailableSessions = new Set<string>();
const deletionListeners = new Set<(sessionId: string) => void>();

export class SessionDeletionError extends Error {
  constructor() {
    super('session_deleted');
    this.name = 'SessionDeletionError';
  }
}

export type SessionDeletionListener = (sessionId: string) => void;

export function subscribeToSessionDeletion(listener: SessionDeletionListener): () => void {
  deletionListeners.add(listener);
  return () => {
    deletionListeners.delete(listener);
  };
}

export function beginSessionDeletion(sessionId: string): void {
  if (unavailableSessions.has(sessionId)) {
    return;
  }
  deletionVersions.set(sessionId, (deletionVersions.get(sessionId) ?? 0) + 1);
  unavailableSessions.add(sessionId);
  for (const listener of [...deletionListeners]) {
    listener(sessionId);
  }
}

export function rollbackSessionDeletion(sessionId: string): void {
  unavailableSessions.delete(sessionId);
}

export function isSessionUnavailable(sessionId: string): boolean {
  return unavailableSessions.has(sessionId);
}

export function getSessionDeletionVersion(sessionId: string): number {
  return deletionVersions.get(sessionId) ?? 0;
}

export function didSessionDeletionStart(sessionId: string, version: number): boolean {
  return getSessionDeletionVersion(sessionId) !== version;
}

export function isSessionDeletionError(error: unknown): error is SessionDeletionError {
  return error instanceof SessionDeletionError;
}

export function resetSessionDeletionLifecycle(): void {
  deletionVersions.clear();
  unavailableSessions.clear();
  deletionListeners.clear();
}
