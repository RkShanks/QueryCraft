export interface PermissionBearingUser {
  permissions?: string[] | null;
}

export function hasPermission(
  user: PermissionBearingUser | null | undefined,
  permission: string
): boolean {
  return user?.permissions?.includes(permission) === true;
}
