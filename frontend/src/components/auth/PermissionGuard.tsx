import React from 'react';
import { Navigate } from 'react-router-dom';
import { useCurrentUser } from '../../hooks/useAuth';
import { hasPermission } from '../../auth/permissions';

interface PermissionGuardProps {
  children: React.ReactNode;
  permission: string;
}

export const PermissionGuard: React.FC<PermissionGuardProps> = ({ children, permission }) => {
  const { data: response, isLoading } = useCurrentUser();

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div
          className="w-8 h-8 border-4 border-indigo-200 border-t-indigo-600 rounded-full animate-spin"
          data-testid="loading-spinner"
        />
      </div>
    );
  }

  const user = response?.data;
  if (!user) {
    return <Navigate to="/sign-in" replace />;
  }

  if (!hasPermission(user, permission)) {
    return <Navigate to="/" replace />;
  }

  return <>{children}</>;
};
