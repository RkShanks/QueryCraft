import React from 'react';

export interface ConnectionActionsProps {
  connectionId: string;
  lifecycleState: 'active' | 'disabled';
  disabled?: boolean;
  onSuccess?: () => void;
  onError?: (error: unknown) => void;
}

export const ConnectionActions: React.FC<ConnectionActionsProps> = () => {
  return (
    <div>
      {/* Skeleton */}
    </div>
  );
};
