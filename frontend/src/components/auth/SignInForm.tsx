import React, { useState } from 'react';
import { useSignIn } from '../../hooks/useAuth';
import { useTranslation } from 'react-i18next';

export const SignInForm: React.FC = () => {
  const { t } = useTranslation();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const signInMutation = useSignIn();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username) {
      setError(t('error.validation.questionEmpty', { defaultValue: 'Username is required' }));
      return;
    }
    setError('');

    try {
      await signInMutation.mutateAsync({ username, password });
    } catch (err: any) {
      setError(t('auth.signIn.error.invalidCredentials', { defaultValue: 'Invalid credentials' }));
    }
  };

  return (
    <form onSubmit={handleSubmit} className="sign-in-form flex flex-col gap-4">
      <div>
        <label htmlFor="username">{t('auth.signIn.usernameLabel', { defaultValue: 'Username' })}</label>
        <input
          id="username"
          type="text"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          className="border p-2"
        />
      </div>
      <div>
        <label htmlFor="password">{t('auth.signIn.passwordLabel', { defaultValue: 'Password' })}</label>
        <input
          id="password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="border p-2"
        />
      </div>
      {error && <div className="error text-red-500">{error}</div>}
      <button 
        type="submit" 
        disabled={signInMutation.isPending}
        className="bg-blue-500 text-white p-2"
      >
        {signInMutation.isPending ? t('auth.signIn.loading', { defaultValue: 'Signing in...' }) : t('auth.signIn.submitButton', { defaultValue: 'Sign in' })}
      </button>
    </form>
  );
};
