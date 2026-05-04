import React from 'react';
import { SignInForm } from '../components/auth/SignInForm';
import { useTranslation } from 'react-i18next';

export const SignInPage: React.FC = () => {
  const { t } = useTranslation();

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
