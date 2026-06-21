import React from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { useUIStore } from '../../stores/uiStore';
import { useSessionsList } from '../../hooks/useSessions';
import { useSignOut, useCurrentUser } from '../../hooks/useAuth';
import { SessionItem } from './SessionItem';
import { UndoToast, type UndoToastItem } from './UndoToast';
import { Shield } from 'lucide-react';
import {
  Plus,
  PanelLeftClose,
  PanelLeftOpen,
  Sparkles,
  Settings,
  MessageSquare,
  LogOut,
  Database,
} from '../icons';
import './Sidebar.css';

function groupSessionsByDate(
  sessions: Array<{
    id: string;
    preview_text: string | null;
    created_at: string;
    last_activity_at: string;
  }>
) {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const sevenDaysAgo = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000);

  const todayGroup: typeof sessions = [];
  const previous7Group: typeof sessions = [];
  const olderGroup: typeof sessions = [];

  for (const session of sessions) {
    const activity = new Date(session.last_activity_at);
    if (activity >= today) {
      todayGroup.push(session);
    } else if (activity >= sevenDaysAgo) {
      previous7Group.push(session);
    } else {
      olderGroup.push(session);
    }
  }

  return { todayGroup, previous7Group, olderGroup };
}

export const Sidebar: React.FC = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const sidebarCollapsed = useUIStore((state) => state.sidebarCollapsed);
  const toggleSidebar = useUIStore((state) => state.toggleSidebar);
  const activeSessionId = useUIStore((state) => state.activeSessionId);
  const setActiveSessionId = useUIStore((state) => state.setActiveSessionId);
  const [toasts, setToasts] = React.useState<UndoToastItem[]>([]);
  const signOutMutation = useSignOut();
  const { data: userResponse } = useCurrentUser();
  const user = userResponse?.data;

  const hasConnectionsPermission =
    user?.role === 'admin' ||
    user?.role_name === 'admin' ||
    user?.permissions?.includes('admin.connections.manage');

  const hasRolesPermission =
    user?.role === 'admin' ||
    user?.role_name === 'admin' ||
    user?.permissions?.includes('admin.roles.manage');

  const hasAuditPermission =
    user?.role === 'admin' ||
    user?.role_name === 'admin' ||
    user?.permissions?.includes('admin.audit.verify');

  const hasQuotasPermission =
    user?.role === 'admin' ||
    user?.role_name === 'admin' ||
    user?.permissions?.includes('admin.quotas.manage');


  const { data, isLoading } = useSessionsList();
  const deletingSessionIds = React.useMemo(() => new Set(toasts.map((t) => t.sessionId)), [toasts]);
  const sessions = React.useMemo(() => {
    return (data?.items ?? []).filter((s) => !deletingSessionIds.has(s.id));
  }, [data?.items, deletingSessionIds]);

  const { todayGroup, previous7Group, olderGroup } = React.useMemo(
    () => groupSessionsByDate(sessions),
    [sessions]
  );

  const handleNewChat = () => {
    setActiveSessionId(null);
    navigate('/');
  };

  const handleSessionClick = (sessionId: string) => {
    setActiveSessionId(sessionId);
    navigate('/');
  };

  const handleDeleteSession = (sessionId: string) => {
    if (activeSessionId === sessionId) {
      setActiveSessionId(null);
    }
    setToasts((prev) => [
      ...prev,
      {
        id: `${sessionId}-${Date.now()}`,
        sessionId,
        message: t('sidebar.deleteConfirm'),
      },
    ]);
  };

  const handleUndo = (toastId: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== toastId));
  };

  const handleToastExpired = (toastId: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== toastId));
  };

  const handleSignOut = () => {
    signOutMutation.mutate(undefined as never, {
      onSuccess: () => {
        navigate('/sign-in');
      },
    });
  };

  return (
    <div className="sidebar" data-testid="sidebar">
      <div className="sidebar-header">
        <button
          className="sidebar-toggle"
          onClick={toggleSidebar}
          aria-label={sidebarCollapsed ? t('sidebar.expand') : t('sidebar.collapse')}
          data-testid="sidebar-toggle"
        >
          {sidebarCollapsed ? <PanelLeftOpen className="w-5 h-5" /> : <PanelLeftClose className="w-5 h-5" />}
        </button>
        {!sidebarCollapsed && (
          <div className="sidebar-logo">
            <Sparkles className="w-5 h-5" />
            <span className="sidebar-logo-text">{t('app.title')}</span>
          </div>
        )}
      </div>

      <div className="sidebar-new-chat">
        <button
          className="sidebar-new-chat-btn"
          onClick={handleNewChat}
          data-testid="sidebar-new-chat"
        >
          <Plus className="w-4 h-4" />
          {!sidebarCollapsed && t('sidebar.newChat')}
        </button>
      </div>

      <div className="sidebar-nav-buttons">
        <button
          className="sidebar-nav-btn"
          onClick={() => navigate('/history')}
          aria-label={t('nav.history')}
          data-testid="sidebar-nav-history"
        >
          <MessageSquare className="w-4 h-4" />
          {!sidebarCollapsed && t('nav.history')}
        </button>
        <button
          className="sidebar-nav-btn"
          onClick={() => navigate('/settings')}
          aria-label={t('nav.settings')}
          data-testid="sidebar-nav-settings"
        >
          <Settings className="w-4 h-4" />
          {!sidebarCollapsed && t('nav.settings')}
        </button>
        {hasConnectionsPermission && (
          <button
            className="sidebar-nav-btn"
            onClick={() => navigate('/admin/connections')}
            aria-label={t('nav.adminConnections')}
            data-testid="sidebar-nav-connections"
          >
            <Database className="w-4 h-4" />
            {!sidebarCollapsed && t('nav.adminConnections')}
          </button>
        )}
        {hasRolesPermission && (
          <button
            className="sidebar-nav-btn"
            onClick={() => navigate('/admin/roles')}
            aria-label={t('nav.adminRoles') || 'Roles'}
            data-testid="sidebar-nav-roles"
          >
            <Shield className="w-4 h-4" />
            {!sidebarCollapsed && (t('nav.adminRoles') || 'Roles')}
          </button>
        )}
        {hasAuditPermission && (
          <button
            className="sidebar-nav-btn"
            onClick={() => navigate('/admin/audit')}
            aria-label={t('nav.adminAudit') || 'Audit Verification'}
            data-testid="sidebar-nav-audit"
          >
            <Shield className="w-4 h-4" />
            {!sidebarCollapsed && (t('nav.adminAudit') || 'Audit Verification')}
          </button>
        )}
        {hasQuotasPermission && (
          <button
            className="sidebar-nav-btn"
            onClick={() => navigate('/admin/quotas')}
            aria-label={t('nav.adminQuotas') || 'Quotas'}
            data-testid="sidebar-nav-quotas"
          >
            <Shield className="w-4 h-4" />
            {!sidebarCollapsed && (t('nav.adminQuotas') || 'Quotas')}
          </button>
        )}

      </div>

      <div className="sidebar-sessions">
        {isLoading ? (
          <div className="sidebar-loading">{t('history.loading')}</div>
        ) : sessions.length === 0 ? (
          <div className="sidebar-empty">{t('sidebar.empty')}</div>
        ) : (
          <>
            {!sidebarCollapsed && todayGroup.length > 0 && (
              <div className="sidebar-group">
                <h3 className="sidebar-group-title">{t('sidebar.today')}</h3>
                {todayGroup.map((session) => (
                  <SessionItem
                    key={session.id}
                    session={session}
                    isActive={session.id === activeSessionId}
                    onClick={() => handleSessionClick(session.id)}
                    onDelete={() => handleDeleteSession(session.id)}
                  />
                ))}
              </div>
            )}
            {!sidebarCollapsed && previous7Group.length > 0 && (
              <div className="sidebar-group">
                <h3 className="sidebar-group-title">{t('sidebar.previous7Days')}</h3>
                {previous7Group.map((session) => (
                  <SessionItem
                    key={session.id}
                    session={session}
                    isActive={session.id === activeSessionId}
                    onClick={() => handleSessionClick(session.id)}
                    onDelete={() => handleDeleteSession(session.id)}
                  />
                ))}
              </div>
            )}
            {!sidebarCollapsed && olderGroup.length > 0 && (
              <div className="sidebar-group">
                <h3 className="sidebar-group-title">{t('sidebar.older')}</h3>
                {olderGroup.map((session) => (
                  <SessionItem
                    key={session.id}
                    session={session}
                    isActive={session.id === activeSessionId}
                    onClick={() => handleSessionClick(session.id)}
                    onDelete={() => handleDeleteSession(session.id)}
                  />
                ))}
              </div>
            )}
            {sidebarCollapsed &&
              sessions.map((session) => (
                <SessionItem
                  key={session.id}
                  session={session}
                  isActive={session.id === activeSessionId}
                  onClick={() => handleSessionClick(session.id)}
                  onDelete={() => handleDeleteSession(session.id)}
                  collapsed
                />
              ))}
          </>
        )}
      </div>

      <div className="sidebar-footer">
        <button
          className="sidebar-sign-out-btn"
          onClick={handleSignOut}
          aria-label={t('nav.signOut')}
          data-testid="sidebar-sign-out"
          disabled={signOutMutation.isPending}
        >
          <LogOut className="w-4 h-4" />
          {!sidebarCollapsed && t('nav.signOut')}
        </button>
      </div>

      <div className="undo-toast-container">
        {toasts.map((toast) => (
          <UndoToast
            key={toast.id}
            item={toast}
            onUndo={() => handleUndo(toast.id)}
            onExpired={() => handleToastExpired(toast.id)}
          />
        ))}
      </div>
    </div>
  );
};
