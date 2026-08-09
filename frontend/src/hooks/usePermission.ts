import {
  hasPermission,
  type Permission,
} from '../auth/permissions';
import { useCurrentUser } from './useAuth';

export class PermissionRequiredError extends Error {
  readonly code = 'permission_required';

  constructor(readonly permission: Permission) {
    super(`Permission required: ${permission}`);
    this.name = 'PermissionRequiredError';
  }
}

export function usePermission(permission: Permission): boolean {
  const { data: response } = useCurrentUser();
  return hasPermission(response?.data, permission);
}

export function useAnyPermission(permissions: readonly Permission[]): boolean {
  const { data: response } = useCurrentUser();
  return permissions.some((permission) => hasPermission(response?.data, permission));
}

export function requirePermission(granted: boolean, permission: Permission): void {
  if (!granted) {
    throw new PermissionRequiredError(permission);
  }
}
