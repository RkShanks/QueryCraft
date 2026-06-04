import React from 'react';

interface PermissionGuardProps {
  children: React.ReactNode;
  permission: string;
}

export const PermissionGuard: React.FC<PermissionGuardProps> = ({ children }) => {
  return <div data-testid="permission-guard-stub">{children}</div>;
};
