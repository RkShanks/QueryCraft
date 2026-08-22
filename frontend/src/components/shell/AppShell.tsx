import React from 'react';
import { useTranslation } from 'react-i18next';
import { useUIStore } from '../../stores/uiStore';
import { Sidebar } from '../sidebar/Sidebar';
import { LanguageToggle } from '../common/LanguageToggle';
import { directionFor, normalizeAppLanguage } from '../../i18n/locale';
import './AppShell.css';

interface AppShellProps {
  children: React.ReactNode;
}

export const AppShell: React.FC<AppShellProps> = ({ children }) => {
  const { i18n } = useTranslation();
  const sidebarCollapsed = useUIStore((state) => state.sidebarCollapsed);
  const collapseSidebar = useUIStore((state) => state.collapseSidebar);
  const dir = directionFor(normalizeAppLanguage(i18n.resolvedLanguage ?? i18n.language) ?? 'en');

  React.useLayoutEffect(() => {
    if (window.innerWidth <= 768) {
      collapseSidebar();
    }
  }, [collapseSidebar]);

  return (
    <div
      className={`app-shell ${sidebarCollapsed ? 'sidebar-collapsed' : ''}`}
      dir={dir}
      data-testid="app-shell"
    >
      <aside className="app-shell-sidebar" data-testid="app-shell-sidebar">
        <Sidebar />
        <div className="app-shell-locale-toggle" data-testid="app-shell-language">
          <LanguageToggle />
        </div>
      </aside>
      <main className="app-shell-workspace" data-testid="app-shell-workspace">
        {children}
      </main>
    </div>
  );
};
