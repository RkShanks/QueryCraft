import { describe, expect, it } from 'vitest';
import {
  firstPermittedRoute,
  PERMISSIONS,
  PROTECTED_ROUTE_CATALOG,
  type Permission,
  type ProtectedRoutePath,
} from './permissions';

const lockedRoutePermissions: Record<ProtectedRoutePath, Permission> = {
  '/': PERMISSIONS.QUERY_SUBMIT,
  '/ask': PERMISSIONS.QUERY_SUBMIT,
  '/history': PERMISSIONS.QUERY_HISTORY_VIEW,
  '/settings': PERMISSIONS.ADMIN_CONNECTIONS_MANAGE,
  '/admin/connections': PERMISSIONS.ADMIN_CONNECTIONS_MANAGE,
  '/admin/roles': PERMISSIONS.ADMIN_ROLES_MANAGE,
  '/admin/sso': PERMISSIONS.ADMIN_SSO_MANAGE,
  '/admin/audit': PERMISSIONS.ADMIN_AUDIT_VERIFY,
  '/admin/quotas': PERMISSIONS.ADMIN_QUOTAS_MANAGE,
  '/admin/detection': PERMISSIONS.ADMIN_SECURITY_MANAGE,
};

const lockedLandingOrder: Array<[Permission, ProtectedRoutePath]> = [
  [PERMISSIONS.QUERY_SUBMIT, '/'],
  [PERMISSIONS.QUERY_HISTORY_VIEW, '/history'],
  [PERMISSIONS.ADMIN_CONNECTIONS_MANAGE, '/admin/connections'],
  [PERMISSIONS.ADMIN_ROLES_MANAGE, '/admin/roles'],
  [PERMISSIONS.ADMIN_SSO_MANAGE, '/admin/sso'],
  [PERMISSIONS.ADMIN_AUDIT_VERIFY, '/admin/audit'],
  [PERMISSIONS.ADMIN_QUOTAS_MANAGE, '/admin/quotas'],
  [PERMISSIONS.ADMIN_SECURITY_MANAGE, '/admin/detection'],
];

describe('permission catalog route contract', () => {
  it('maps every protected route to the exact backend permission', () => {
    expect(
      Object.fromEntries(
        PROTECTED_ROUTE_CATALOG.map(({ path, permission }) => [path, permission])
      )
    ).toEqual(lockedRoutePermissions);
  });

  it.each(lockedLandingOrder)('lands %s users on %s', (permission, path) => {
    expect(firstPermittedRoute({ permissions: [permission] })).toBe(path);
  });

  it('selects the first permitted landing route and denies empty or spoofed roles', () => {
    expect(
      firstPermittedRoute({
        permissions: [
          PERMISSIONS.ADMIN_SECURITY_MANAGE,
          PERMISSIONS.QUERY_HISTORY_VIEW,
        ],
      })
    ).toBe('/history');
    expect(firstPermittedRoute({ permissions: [] })).toBeNull();
    expect(firstPermittedRoute({ permissions: undefined })).toBeNull();
  });
});
