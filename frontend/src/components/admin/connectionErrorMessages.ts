const KNOWN_SAFE_KEYS = [
  'error.connection_auth_failed',
  'error.connection_network_unreachable',
  'error.connection_timeout',
  'error.credential_config',
  'error.introspection_failed',
  'error.introspection_timeout',
  'error.connection_referenced_delete_blocked',
  'error.connection_already_active',
  'error.connection_already_disabled',
  'error.connection_not_found',
  'error.connection_disabled',
  'error.unknown.message',
];

const mapCategoryToKey = (category?: string | null): string => {
  if (!category) return 'error.unknown.message';
  const clean = category.toLowerCase().trim();
  
  if (clean === 'auth_failed' || clean === 'connection_auth_failed') {
    return 'error.connection_auth_failed';
  }
  if (clean === 'network_unreachable' || clean === 'connection_network_unreachable') {
    return 'error.connection_network_unreachable';
  }
  if (clean === 'timeout' || clean === 'connection_timeout') {
    return 'error.connection_timeout';
  }
  if (clean === 'credential_config') {
    return 'error.credential_config';
  }
  if (clean === 'introspection_failed') {
    return 'error.introspection_failed';
  }
  if (clean === 'introspection_timeout') {
    return 'error.introspection_timeout';
  }
  if (clean === 'connection_referenced_delete_blocked' || clean === 'referenced_delete_blocked') {
    return 'error.connection_referenced_delete_blocked';
  }
  if (clean === 'connection_already_active') {
    return 'error.connection_already_active';
  }
  if (clean === 'connection_already_disabled') {
    return 'error.connection_already_disabled';
  }
  if (clean === 'connection_not_found') {
    return 'error.connection_not_found';
  }
  if (clean === 'connection_disabled') {
    return 'error.connection_disabled';
  }
  return 'error.unknown.message';
};

const getSafeMessageKey = (key?: string | null): string => {
  if (key && KNOWN_SAFE_KEYS.includes(key)) {
    return key;
  }
  return 'error.unknown.message';
};

export const getSafeConnectionErrorKey = (error: unknown): string => {
  if (!error) return 'error.unknown.message';

  // If it is a string itself
  if (typeof error === 'string') {
    return mapCategoryToKey(error);
  }

  const obj = error as Record<string, unknown>;

  // Check if message_key is directly on the error object
  if (typeof obj.message_key === 'string') {
    return getSafeMessageKey(obj.message_key);
  }

  // Check if error is directly on the error object (e.g. { error: "connection_auth_failed" })
  if (typeof obj.error === 'string') {
    return mapCategoryToKey(obj.error);
  }

  // If there is a body field (e.g. from SDK / Fetch response error)
  if (obj.body && typeof obj.body === 'object') {
    const body = obj.body as Record<string, unknown>;
    if (typeof body.message_key === 'string') {
      return getSafeMessageKey(body.message_key);
    }
    if (typeof body.error === 'string') {
      return mapCategoryToKey(body.error);
    }
    if (typeof body.detail === 'string') {
      return mapCategoryToKey(body.detail);
    }
    if (body.detail && typeof body.detail === 'object') {
      const detail = body.detail as Record<string, unknown>;
      if (typeof detail.message_key === 'string') {
        return getSafeMessageKey(detail.message_key);
      }
      if (typeof detail.error === 'string') {
        return mapCategoryToKey(detail.error);
      }
    }
  }

  // If there is a detail field
  if (typeof obj.detail === 'string') {
    return mapCategoryToKey(obj.detail);
  }
  if (obj.detail && typeof obj.detail === 'object') {
    const detail = obj.detail as Record<string, unknown>;
    if (typeof detail.message_key === 'string') {
      return getSafeMessageKey(detail.message_key);
    }
    if (typeof detail.error === 'string') {
      return mapCategoryToKey(detail.error);
    }
  }

  return 'error.unknown.message';
};
