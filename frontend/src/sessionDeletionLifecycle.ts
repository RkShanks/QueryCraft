const deletionVersions = new Map<string, number>();
const unavailableSessions = new Set<string>();

export class SessionDeletionError extends Error {
  constructor() {
    super('session_deleted');
    this.name = 'SessionDeletionError';
  }
}

export function beginSessionDeletion(sessionId: string): void {
  if (unavailableSessions.has(sessionId)) return;
  deletionVersions.set(sessionId, (deletionVersions.get(sessionId) ?? 0) + 1);
  unavailableSessions.add(sessionId);
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
}
