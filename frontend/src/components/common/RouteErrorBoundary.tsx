import { Component } from 'react';
import type { ErrorInfo, ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { AlertTriangle, RefreshCw } from 'lucide-react';
import { firstPermittedRoute, type PermissionBearingUser } from '../../auth/permissions';
import { useAuthSessionContext } from '../../auth/AuthSessionContext';

interface BoundaryInnerProps {
  children: ReactNode;
  translatedTitle: string;
  retryLabel: string;
  homeLabel: string | null;
  onHome: (() => void) | null;
}

interface BoundaryInnerState {
  error: Error | null;
}

/**
 * Renders a sanitized, localized fallback when the wrapped route subtree
 * throws. Raw error detail never reaches the DOM or console channels owned by
 * the UI; Retry re-renders the subtree and the optional home action performs a
 * permission-aware safe navigation.
 */
class RouteErrorBoundaryInner extends Component<BoundaryInnerProps, BoundaryInnerState> {
  state: BoundaryInnerState = { error: null };

  static getDerivedStateFromError(error: Error): BoundaryInnerState {
    return { error };
  }

  componentDidCatch(_error: Error, _info: ErrorInfo) {
    // Deliberately silent: stack/error text must not reach browser channels.
  }

  private reset = () => {
    this.setState({ error: null });
  };

  render() {
    const { children, translatedTitle, retryLabel, homeLabel, onHome } = this.props;
    if (!this.state.error) {
      return children;
    }
    return (
      <div
        role="alert"
        data-testid="route-error-boundary"
        className="m-4 flex flex-col items-center justify-center gap-4 rounded-xl border border-red-500/20 bg-red-500/5 p-8 text-center animate-fade-in"
      >
        <AlertTriangle className="h-10 w-10 text-red-400" aria-hidden="true" />
        <p className="text-base font-semibold text-red-300">{translatedTitle}</p>
        <div className="flex flex-wrap items-center justify-center gap-3">
          <button
            type="button"
            onClick={this.reset}
            className="inline-flex min-h-10 items-center justify-center gap-2 rounded-lg border border-red-400/30 bg-red-500/10 px-4 py-2 text-sm font-semibold text-red-200 transition-colors hover:border-red-300 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-300"
          >
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
            {retryLabel}
          </button>
          {onHome && homeLabel && (
            <button
              type="button"
              onClick={onHome}
              className="inline-flex min-h-10 items-center justify-center rounded-lg border border-obsidian-700 bg-obsidian-900 px-4 py-2 text-sm font-semibold text-text-secondary transition-colors hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-neon-cyan"
            >
              {homeLabel}
            </button>
          )}
        </div>
      </div>
    );
  }
}

export interface RouteErrorBoundaryProps {
  children: ReactNode;
}

/**
 * Function shell so the boundary can consume router/i18n/identity hooks while
 * keeping the actual error capture in a class boundary. Key the rendered
 * instance by location key so deliberate navigation replaces a failed state.
 */
export function RouteErrorBoundary({ children }: RouteErrorBoundaryProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const authSession = useAuthSessionContext();
  const user = (authSession?.currentUserQuery.data as { data?: PermissionBearingUser } | undefined)
    ?.data ?? null;
  const landingRoute = firstPermittedRoute(user);

  return (
    <RouteErrorBoundaryInner
      translatedTitle={t('routeError.title')}
      retryLabel={t('common.retry')}
      homeLabel={landingRoute ? t('routeError.home') : null}
      onHome={
        landingRoute
          ? () => {
              navigate(landingRoute);
            }
          : null
      }
    >
      {children}
    </RouteErrorBoundaryInner>
  );
}
