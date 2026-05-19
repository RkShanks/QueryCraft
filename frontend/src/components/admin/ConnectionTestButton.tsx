import React from 'react';

export interface ConnectionTestButtonProps {
  connectionId: string;
  disabled?: boolean;
  onSuccess?: () => void;
  onError?: (error: unknown) => void;
}

export const ConnectionTestButton: React.FC<ConnectionTestButtonProps> = () => {
  return <div>Stub</div>;
};
