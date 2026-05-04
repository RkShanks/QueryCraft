import React from 'react';
import { Navigate } from 'react-router-dom';
import { SignInForm } from '../components/auth/SignInForm';
import { useTranslation } from 'react-i18next';
import { useCurrentUser } from '../hooks/useAuth';

export const SignInPage: React.FC = () => {
  const { t } = useTranslation();
  const { data: user, isLoading } = useCurrentUser();

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-8 h-8 border-4 border-indigo-200 border-t-indigo-600 rounded-full animate-spin" />
      </div>
    );
  }

  if (user) {
    return <Navigate to="/" replace />;
  }

  return (
    <div className="sign-in-page min-h-screen flex items-center justify-center bg-gray-50">
      <div className="max-w-md w-full p-6 bg-white shadow-md rounded-lg">
        <h1 className="text-2xl font-bold mb-6 text-center">
          {t('auth.signIn.title', { defaultValue: 'Sign in to QueryCraft' })}
        </h1>
        <SignInForm />
      </div>
    </div>
  );
};
