import { beforeEach, describe, expect, it } from 'vitest';
import {
  beginSessionDeletion,
  didSessionDeletionStart,
  getSessionDeletionVersion,
  isSessionUnavailable,
  resetSessionDeletionLifecycle,
  rollbackSessionDeletion,
} from './sessionDeletionLifecycle';

describe('session deletion lifecycle', () => {
  beforeEach(() => resetSessionDeletionLifecycle());

  it('suppresses pre-existing work even when a failed DELETE rolls back', () => {
    const sessionId = 'session-1';
    const versionBeforeDelete = getSessionDeletionVersion(sessionId);

    beginSessionDeletion(sessionId);
    rollbackSessionDeletion(sessionId);

    expect(isSessionUnavailable(sessionId)).toBe(false);
    expect(didSessionDeletionStart(sessionId, versionBeforeDelete)).toBe(true);
    expect(didSessionDeletionStart(sessionId, getSessionDeletionVersion(sessionId))).toBe(false);
  });

  it('marks one deletion start once when the mutation also calls begin', () => {
    const sessionId = 'session-1';
    beginSessionDeletion(sessionId);
    const firstVersion = getSessionDeletionVersion(sessionId);

    beginSessionDeletion(sessionId);

    expect(getSessionDeletionVersion(sessionId)).toBe(firstVersion);
    expect(isSessionUnavailable(sessionId)).toBe(true);
  });
});
