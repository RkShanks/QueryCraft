import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useLocation } from 'react-router-dom';

const titleKeyByPath: Readonly<Record<string, string>> = {
  '/sign-in': 'documentTitle.signIn',
  '/': 'documentTitle.workspace',
  '/ask': 'documentTitle.ask',
  '/history': 'documentTitle.history',
  '/settings': 'documentTitle.settings',
  '/admin/connections': 'documentTitle.adminConnections',
  '/admin/roles': 'documentTitle.adminRoles',
  '/admin/sso': 'documentTitle.adminSso',
  '/admin/audit': 'documentTitle.adminAudit',
  '/admin/quotas': 'documentTitle.adminQuotas',
  '/admin/detection': 'documentTitle.adminDetection',
  '/access-denied': 'documentTitle.accessDenied',
};

export function DocumentTitle() {
  const { pathname } = useLocation();
  const { t } = useTranslation();
  const pageTitleKey = titleKeyByPath[pathname];
  const applicationTitle = t('app.title');
  const documentTitle = pageTitleKey
    ? `${t(pageTitleKey)} | ${applicationTitle}`
    : applicationTitle;

  useEffect(() => {
    document.title = documentTitle;
  }, [documentTitle]);

  return null;
}
