import { LogOut, ShieldX } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useSignOut } from '../hooks/useAuth';

export function AccessDeniedPage() {
  const { t } = useTranslation();
  const signOut = useSignOut();

  return (
    <main className="min-h-screen bg-obsidian-950 px-4 flex items-center justify-center">
      <section
        className="w-full max-w-lg rounded-2xl border border-obsidian-800 bg-obsidian-900/80 p-8 text-center shadow-2xl"
        aria-labelledby="access-denied-title"
      >
        <ShieldX className="mx-auto h-12 w-12 text-amber-400" aria-hidden="true" />
        <h1 id="access-denied-title" className="mt-5 text-2xl font-semibold text-white">
          {t('accessDenied.title')}
        </h1>
        <p className="mt-3 text-sm leading-6 text-obsidian-300">
          {t('accessDenied.description')}
        </p>
        {signOut.isError && (
          <>
            <p className="mt-5 rounded-lg border border-red-900/50 bg-red-950/30 p-3 text-sm text-red-300" role="alert">
              {t('accessDenied.signOutFailed')}
            </p>
            <button
              type="button"
              className="mt-3 inline-flex min-h-11 items-center justify-center rounded-lg border border-obsidian-700 px-5 py-2.5 font-semibold text-obsidian-100 focus:outline-none focus:ring-2 focus:ring-neon-cyan focus:ring-offset-2 focus:ring-offset-obsidian-950 disabled:opacity-50"
              onClick={() => signOut.mutate()}
              disabled={signOut.isPending}
            >
              {t('common.retry')}
            </button>
          </>
        )}
        <button
          type="button"
          className="mt-6 inline-flex min-h-11 items-center justify-center gap-2 rounded-lg bg-neon-cyan px-5 py-2.5 font-semibold text-obsidian-950 focus:outline-none focus:ring-2 focus:ring-neon-cyan focus:ring-offset-2 focus:ring-offset-obsidian-950 disabled:opacity-50"
          onClick={() => signOut.mutate()}
          disabled={signOut.isPending}
          aria-label={t('nav.signOut')}
        >
          <LogOut className="h-4 w-4" aria-hidden="true" />
          {signOut.isPending ? t('accessDenied.signingOut') : t('nav.signOut')}
        </button>
      </section>
    </main>
  );
}
