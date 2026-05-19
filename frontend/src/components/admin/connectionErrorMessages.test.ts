import { describe, it, expect } from 'vitest';
import { getSafeConnectionErrorKey } from './connectionErrorMessages';

describe('getSafeConnectionErrorKey', () => {
  it('maps credential_config category to credential_config translation key', () => {
    expect(getSafeConnectionErrorKey({ error: 'credential_config' })).toBe('error.credential_config');
    expect(getSafeConnectionErrorKey({ message_key: 'error.credential_config' })).toBe('error.credential_config');
  });

  it('maps connection_auth_failed and auth_failed to connection_auth_failed translation key', () => {
    expect(getSafeConnectionErrorKey({ error: 'connection_auth_failed' })).toBe('error.connection_auth_failed');
    expect(getSafeConnectionErrorKey({ error: 'auth_failed' })).toBe('error.connection_auth_failed');
    expect(getSafeConnectionErrorKey({ message_key: 'error.connection_auth_failed' })).toBe('error.connection_auth_failed');
  });

  it('maps connection_network_unreachable and network_unreachable to connection_network_unreachable translation key', () => {
    expect(getSafeConnectionErrorKey({ error: 'connection_network_unreachable' })).toBe('error.connection_network_unreachable');
    expect(getSafeConnectionErrorKey({ error: 'network_unreachable' })).toBe('error.connection_network_unreachable');
    expect(getSafeConnectionErrorKey({ message_key: 'error.connection_network_unreachable' })).toBe('error.connection_network_unreachable');
  });

  it('maps introspection_failed to introspection_failed translation key', () => {
    expect(getSafeConnectionErrorKey({ error: 'introspection_failed' })).toBe('error.introspection_failed');
    expect(getSafeConnectionErrorKey({ message_key: 'error.introspection_failed' })).toBe('error.introspection_failed');
  });

  it('maps connection_referenced_delete_blocked and referenced_delete_blocked to delete blocked key', () => {
    expect(getSafeConnectionErrorKey({ error: 'connection_referenced_delete_blocked' })).toBe('error.connection_referenced_delete_blocked');
    expect(getSafeConnectionErrorKey({ error: 'referenced_delete_blocked' })).toBe('error.connection_referenced_delete_blocked');
    expect(getSafeConnectionErrorKey({ message_key: 'error.connection_referenced_delete_blocked' })).toBe('error.connection_referenced_delete_blocked');
  });

  it('maps connection_disabled to connection_disabled key', () => {
    expect(getSafeConnectionErrorKey({ error: 'connection_disabled' })).toBe('error.connection_disabled');
    expect(getSafeConnectionErrorKey({ message_key: 'error.connection_disabled' })).toBe('error.connection_disabled');
  });

  it('handles unknown backend error categories/keys and falls back to generic localized message', () => {
    expect(getSafeConnectionErrorKey({ error: 'some_arbitrary_driver_error_string' })).toBe('error.unknown.message');
    expect(getSafeConnectionErrorKey({ message_key: 'error.unrecognized_message_key_here' })).toBe('error.unknown.message');
  });

  it('extracts nested errors inside detail or body properties', () => {
    expect(getSafeConnectionErrorKey({
      body: {
        detail: {
          error: 'connection_auth_failed'
        }
      }
    })).toBe('error.connection_auth_failed');

    expect(getSafeConnectionErrorKey({
      detail: {
        message_key: 'error.connection_network_unreachable'
      }
    })).toBe('error.connection_network_unreachable');
  });

  it('does not leak driver-like strings, password, or secret keywords', () => {
    const sensitiveError = {
      error: 'driver_failed_with_password_123_secret_xyz',
      message: 'Failed database connection at host 127.0.0.1 and password root'
    };
    expect(getSafeConnectionErrorKey(sensitiveError)).toBe('error.unknown.message');
  });
});
