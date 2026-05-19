import React from 'react';

export interface ConnectionFormProps {
  initialValues?: any;
  onSubmit: (data: any) => void;
  onCancel: () => void;
  isSubmitting?: boolean;
}

export const ConnectionForm: React.FC<ConnectionFormProps> = () => {
  return <div data-testid="connection-form-stub">Connection Form Stub</div>;
};
