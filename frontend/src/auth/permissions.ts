export const PERMISSIONS = {
  QUERY_SUBMIT: 'query.submit',
  QUERY_HISTORY_VIEW: 'query.history.view',
  ADMIN_CONNECTIONS_MANAGE: 'admin.connections.manage',
  ADMIN_ROLES_MANAGE: 'admin.roles.manage',
  ADMIN_SSO_MANAGE: 'admin.sso.manage',
  ADMIN_AUDIT_VERIFY: 'admin.audit.verify',
  ADMIN_QUOTAS_MANAGE: 'admin.quotas.manage',
  ADMIN_SECURITY_MANAGE: 'admin.security.manage',
} as const;

export type Permission = (typeof PERMISSIONS)[keyof typeof PERMISSIONS];

export type ProtectedRoutePath =
  | '/'
  | '/ask'
  | '/history'
  | '/settings'
  | '/admin/connections'
  | '/admin/roles'
  | '/admin/sso'
  | '/admin/audit'
  | '/admin/quotas'
  | '/admin/detection';

export interface PermissionRouteDefinition {
  path: ProtectedRoutePath;
  landingOrder?: number;
  navigation?: {
    id: string;
    labelKey: string;
  };
}

export interface PermissionCatalogEntry {
  permission: Permission;
  labelKey: string;
  descriptionKey: string;
  routes: readonly PermissionRouteDefinition[];
}

export const PERMISSION_CATALOG: readonly PermissionCatalogEntry[] = [
  {
    permission: PERMISSIONS.QUERY_SUBMIT,
    labelKey: 'admin.roles.permissions.query.submit',
    descriptionKey: 'admin.roles.permissions.query.submit.desc',
    routes: [
      { path: '/', landingOrder: 0, navigation: { id: 'new-chat', labelKey: 'sidebar.newChat' } },
      { path: '/ask' },
    ],
  },
  {
    permission: PERMISSIONS.QUERY_HISTORY_VIEW,
    labelKey: 'admin.roles.permissions.query.history.view',
    descriptionKey: 'admin.roles.permissions.query.history.view.desc',
    routes: [
      { path: '/history', landingOrder: 1, navigation: { id: 'history', labelKey: 'nav.history' } },
    ],
  },
  {
    permission: PERMISSIONS.ADMIN_CONNECTIONS_MANAGE,
    labelKey: 'admin.roles.permissions.admin.connections.manage',
    descriptionKey: 'admin.roles.permissions.admin.connections.manage.desc',
    routes: [
      { path: '/settings', navigation: { id: 'settings', labelKey: 'nav.settings' } },
      {
        path: '/admin/connections',
        landingOrder: 2,
        navigation: { id: 'connections', labelKey: 'nav.adminConnections' },
      },
    ],
  },
  {
    permission: PERMISSIONS.ADMIN_ROLES_MANAGE,
    labelKey: 'admin.roles.permissions.admin.roles.manage',
    descriptionKey: 'admin.roles.permissions.admin.roles.manage.desc',
    routes: [
      {
        path: '/admin/roles',
        landingOrder: 3,
        navigation: { id: 'roles', labelKey: 'nav.adminRoles' },
      },
    ],
  },
  {
    permission: PERMISSIONS.ADMIN_SSO_MANAGE,
    labelKey: 'admin.roles.permissions.admin.sso.manage',
    descriptionKey: 'admin.roles.permissions.admin.sso.manage.desc',
    routes: [
      {
        path: '/admin/sso',
        landingOrder: 4,
        navigation: { id: 'sso', labelKey: 'nav.adminSso' },
      },
    ],
  },
  {
    permission: PERMISSIONS.ADMIN_AUDIT_VERIFY,
    labelKey: 'admin.roles.permissions.admin.audit.verify',
    descriptionKey: 'admin.roles.permissions.admin.audit.verify.desc',
    routes: [
      {
        path: '/admin/audit',
        landingOrder: 5,
        navigation: { id: 'audit', labelKey: 'nav.adminAudit' },
      },
    ],
  },
  {
    permission: PERMISSIONS.ADMIN_QUOTAS_MANAGE,
    labelKey: 'admin.roles.permissions.admin.quotas.manage',
    descriptionKey: 'admin.roles.permissions.admin.quotas.manage.desc',
    routes: [
      {
        path: '/admin/quotas',
        landingOrder: 6,
        navigation: { id: 'quotas', labelKey: 'nav.adminQuotas' },
      },
    ],
  },
  {
    permission: PERMISSIONS.ADMIN_SECURITY_MANAGE,
    labelKey: 'admin.roles.permissions.admin.security.manage',
    descriptionKey: 'admin.roles.permissions.admin.security.manage.desc',
    routes: [
      {
        path: '/admin/detection',
        landingOrder: 7,
        navigation: { id: 'detection', labelKey: 'detection.page_title' },
      },
    ],
  },
];

export const PROTECTED_ROUTE_CATALOG = PERMISSION_CATALOG.flatMap(({ permission, routes }) =>
  routes.map((route) => ({ ...route, permission }))
);

export const NAVIGATION_CATALOG = PROTECTED_ROUTE_CATALOG.filter(
  (route): route is typeof route & { navigation: NonNullable<typeof route.navigation> } =>
    route.navigation !== undefined
);

export function firstPermittedRoute(
  user: PermissionBearingUser | null | undefined
): ProtectedRoutePath | null {
  const landingRoutes = PROTECTED_ROUTE_CATALOG
    .filter((route) => route.landingOrder !== undefined && hasPermission(user, route.permission))
    .sort((first, second) => first.landingOrder! - second.landingOrder!);
  return landingRoutes[0]?.path ?? null;
}

const knownPermissions = new Set<Permission>(
  PERMISSION_CATALOG.map(({ permission }) => permission)
);

export interface PermissionBearingUser {
  permissions?: string[] | null;
}

export function isKnownPermission(permission: string): permission is Permission {
  return knownPermissions.has(permission as Permission);
}

export function hasPermission(
  user: PermissionBearingUser | null | undefined,
  permission: Permission
): boolean {
  return user?.permissions?.includes(permission) === true;
}
