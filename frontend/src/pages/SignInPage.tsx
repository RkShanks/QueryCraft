import React from 'react';
import { Navigate } from 'react-router-dom';
import { SignInForm } from '../components/auth/SignInForm';
import { useTranslation } from 'react-i18next';
import { useCurrentUser } from '../hooks/useAuth';
import { Database, Sparkles } from 'lucide-react';

export const SignInPage: React.FC = () => {
  const { t } = useTranslation();
  const { data: user, isLoading } = useCurrentUser();

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-obsidian-950">
        <div className="w-10 h-10 border-4 border-obsidian-800 border-t-neon-cyan rounded-full animate-spin shadow-[0_0_15px_rgba(6,182,212,0.5)]" />
      </div>
    );
  }

  if (user) {
    return <Navigate to="/" replace />;
  }

  return (
    <div className="sign-in-page min-h-screen flex items-center justify-center bg-obsidian-950 p-4 relative overflow-hidden">
      {/* Background Neon Accent Glows */}
      <div className="absolute top-1/4 start-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-neon-cyan-glow/20 blur-[120px] rounded-full pointer-events-none animate-glow-pulse" />
      <div className="absolute bottom-1/4 start-1/3 -translate-x-1/2 -translate-y-1/2 w-80 h-80 bg-neon-purple-glow/20 blur-[100px] rounded-full pointer-events-none" />

      {/* Main Glassmorphic Container */}
      <div className="max-w-md w-full relative z-10 bg-obsidian-900/60 backdrop-blur-xl border border-obsidian-800 rounded-2xl shadow-2xl overflow-hidden animate-fade-in">
        {/* Accent Top Bar */}
        <div className="h-1.5 w-full bg-gradient-to-r from-neon-cyan via-neon-purple to-neon-fuchsia" />
        
        <div className="p-8">
          {/* Brand Header */}
          <div className="flex flex-col items-center gap-2 mb-8">
            <div className="w-12 h-12 rounded-xl bg-gradient-to-r from-neon-cyan to-neon-purple flex items-center justify-center shadow-lg shadow-neon-cyan-glow relative group">
              <Database className="w-6 h-6 text-white" />
              <div className="absolute inset-0 rounded-xl bg-gradient-to-r from-neon-cyan to-neon-purple opacity-0 group-hover:opacity-100 transition-opacity duration-300 blur-sm" />
            </div>
            <div className="text-center mt-2">
              <h1 className="text-3xl font-extrabold tracking-tight bg-gradient-to-r from-white via-obsidian-200 to-obsidian-400 bg-clip-text text-transparent">
                {t('app.title')}
              </h1>
              <p className="text-sm text-obsidian-400 mt-1.5 flex items-center justify-center gap-1">
                <Sparkles className="w-3.5 h-3.5 text-neon-cyan" />
                {t('app.subtitle')}
              </p>
            </div>
          </div>

          <h2 className="text-lg font-semibold text-obsidian-100 mb-6 text-center">
            {t('auth.signIn.title')}
          </h2>

          <SignInForm />
        </div>
      </div>
    </div>
  );
};
