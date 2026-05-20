import React, { useState } from 'react';
import { useSignIn } from '../../hooks/useAuth';
import { useTranslation } from 'react-i18next';
import { User, Lock, Loader2, AlertCircle } from 'lucide-react';

export const SignInForm: React.FC = () => {
  const { t } = useTranslation();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const signInMutation = useSignIn();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username) {
      setError(t('auth.signIn.error.usernameEmpty'));
      return;
    }
    setError('');

    try {
      await signInMutation.mutateAsync({ username, password });
    } catch {
      setError(t('auth.signIn.error.invalidCredentials'));
    }
  };

  return (
    <form onSubmit={handleSubmit} className="sign-in-form flex flex-col gap-5">
      {/* Username Input Field */}
      <div className="flex flex-col gap-1.5">
        <label 
          htmlFor="username" 
          className="text-xs font-semibold text-obsidian-300 uppercase tracking-wider ps-1"
        >
          {t('auth.signIn.username.label')}
        </label>
        <div className="relative">
          <div className="absolute inset-y-0 start-0 ps-3.5 flex items-center pointer-events-none text-obsidian-500">
            <User className="w-4 h-4" />
          </div>
          <input
            id="username"
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            className="w-full bg-obsidian-950/80 border border-obsidian-800 rounded-lg py-2.5 ps-10 pe-4 text-obsidian-200 placeholder-obsidian-600 focus:outline-none focus:border-neon-cyan focus:ring-1 focus:ring-neon-cyan/35 transition-all duration-200"
            placeholder={t('auth.signIn.username.placeholder')}
          />
        </div>
      </div>

      {/* Password Input Field */}
      <div className="flex flex-col gap-1.5">
        <label 
          htmlFor="password" 
          className="text-xs font-semibold text-obsidian-300 uppercase tracking-wider ps-1"
        >
          {t('auth.signIn.password.label')}
        </label>
        <div className="relative">
          <div className="absolute inset-y-0 start-0 ps-3.5 flex items-center pointer-events-none text-obsidian-500">
            <Lock className="w-4 h-4" />
          </div>
          <input
            id="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full bg-obsidian-950/80 border border-obsidian-800 rounded-lg py-2.5 ps-10 pe-4 text-obsidian-200 placeholder-obsidian-600 focus:outline-none focus:border-neon-cyan focus:ring-1 focus:ring-neon-cyan/35 transition-all duration-200"
            placeholder={t('auth.signIn.password.placeholder')}
          />
        </div>
      </div>

      {/* Validation Error Message */}
      {error && (
        <div className="error flex items-center gap-2 text-sm text-red-400 bg-red-950/30 border border-red-900/50 px-3.5 py-2.5 rounded-lg">
          <AlertCircle className="w-4 h-4 shrink-0 text-red-400" />
          <span>{error}</span>
        </div>
      )}

      {/* Submit Button */}
      <button 
        type="submit" 
        disabled={signInMutation.isPending}
        className="w-full mt-2 relative overflow-hidden group rounded-lg py-2.5 px-4 bg-gradient-to-r from-neon-cyan to-neon-purple text-white font-medium hover:brightness-110 active:brightness-95 disabled:opacity-50 disabled:pointer-events-none transition-all duration-200 shadow-lg shadow-neon-cyan-glow flex items-center justify-center gap-2 cursor-pointer"
      >
        {signInMutation.isPending ? (
          <>
            <Loader2 className="w-4 h-4 animate-spin text-white" />
            <span>{t('auth.signIn.signingIn')}</span>
          </>
        ) : (
          <span>{t('auth.signIn.submit')}</span>
        )}
      </button>
    </form>
  );
};
