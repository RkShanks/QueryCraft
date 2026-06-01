import React from 'react';
import { Navigate, useSearchParams } from 'react-router-dom';
import { SignInForm } from '../components/auth/SignInForm';
import { useTranslation } from 'react-i18next';
import { useCurrentUser, useSsoProviders } from '../hooks/useAuth';
import { Database, Sparkles, AlertTriangle, XCircle, Shield } from 'lucide-react';

export const SignInPage: React.FC = () => {
  const { t, i18n } = useTranslation();
  const { data: user, isLoading } = useCurrentUser();
  const { data: providers = [], isLoading: isLoadingProviders } = useSsoProviders();
  const [searchParams] = useSearchParams();

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

  const dir = i18n.language === 'ar' ? 'rtl' : 'ltr';
  const errorParam = searchParams.get('error');

  const getSanitizedErrorMessage = (code: string | null) => {
    if (!code) return null;
    const mappedKeys: Record<string, string> = {
      sso_no_role: 'error.ssoNoRole',
      sso_validation_failed: 'error.ssoValidationFailed',
      sso_provider_unavailable: 'error.ssoProviderUnavailable',
      sso_not_configured: 'error.ssoNotConfigured',
    };
    const key = mappedKeys[code] || 'error.ssoValidationFailed';
    return t(key);
  };

  const ssoError = getSanitizedErrorMessage(errorParam);

  return (
    <div 
      dir={dir}
      className="sign-in-page min-h-screen flex items-center justify-center bg-obsidian-950 p-4 relative overflow-hidden"
    >
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

          {/* Mapped Localized/Sanitized SSO Error Alert */}
          {ssoError && (
            <div className="mb-6 p-4 rounded-xl border border-rose-900/30 bg-rose-950/10 text-sm text-rose-400 flex items-start gap-2.5 animate-shake">
              <XCircle className="w-5 h-5 shrink-0 mt-0.5 text-rose-500" />
              <span className="flex-1">{ssoError}</span>
            </div>
          )}

          <SignInForm />

          {/* SSO Section */}
          {!isLoadingProviders && (
            <>
              {providers.length > 0 ? (
                <>
                  {/* Elegant Or Divider */}
                  <div className="relative my-6">
                    <div className="absolute inset-0 flex items-center" aria-hidden="true">
                      <div className="w-full border-t border-obsidian-800"></div>
                    </div>
                    <div className="relative flex justify-center text-xs text-obsidian-400 uppercase">
                      <span className="bg-obsidian-900/60 px-3 text-obsidian-500 font-semibold tracking-wider">
                        {t('common.or') ?? 'Or'}
                      </span>
                    </div>
                  </div>

                  {/* SSO Buttons list */}
                  <div className="flex flex-col gap-3">
                    {providers.map((provider) => (
                      <button
                        key={provider.display_name}
                        onClick={() => {
                          window.location.href = provider.login_url;
                        }}
                        className="w-full py-2.5 px-4 rounded-xl border border-obsidian-750 bg-obsidian-800/40 text-sm font-semibold text-obsidian-100 hover:bg-obsidian-800/80 hover:border-obsidian-600 focus:outline-none focus:ring-2 focus:ring-neon-cyan focus:ring-offset-2 focus:ring-offset-obsidian-900 transition-all duration-300 flex items-center justify-center gap-2 cursor-pointer active:scale-[0.98]"
                      >
                        <Shield className="w-4 h-4 text-neon-cyan" />
                        <span>
                          {t('auth.signIn.sso.button', { 
                            defaultValue: 'Sign in with {{provider}}', 
                            provider: provider.display_name 
                          })}
                        </span>
                      </button>
                    ))}
                  </div>
                </>
              ) : (
                <>
                  {/* Warning: No SSO Configured message */}
                  <div className="mt-6 p-3.5 rounded-xl border border-amber-900/30 bg-amber-950/10 text-xs text-amber-400/90 flex items-start gap-2.5 animate-fade-in leading-relaxed">
                    <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5 text-amber-500" />
                    <span className="flex-1">
                      {t('error.ssoNotConfigured')}
                    </span>
                  </div>
                </>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
};
