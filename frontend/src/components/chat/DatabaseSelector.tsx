import React, { useState, useRef, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { Database, ChevronDown } from 'lucide-react';
import './DatabaseSelector.css';

export interface UserConnection {
  id: string;
  display_name: string;
  database_type: string;
}

export interface DatabaseSelectorProps {
  connections: UserConnection[];
  selectedId?: string | null;
  onSelect: (connectionId: string) => void;
}

export const DatabaseSelector: React.FC<DatabaseSelectorProps> = ({
  connections,
  selectedId,
  onSelect,
}) => {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const selected = connections.find((c) => c.id === selectedId);

  // Auto-select single connection
  useEffect(() => {
    if (connections.length === 1 && !selectedId) {
      onSelect(connections[0].id);
    }
  }, [connections, selectedId, onSelect]);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    const handleClick = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [open]);

  const handleSelect = useCallback(
    (id: string) => {
      onSelect(id);
      setOpen(false);
    },
    [onSelect]
  );

  if (connections.length === 0) {
    return (
      <div className="database-selector-empty" data-testid="database-selector-empty">
        <Database className="w-4 h-4 text-obsidian-400" />
        <span className="text-sm text-obsidian-400">
          {t('databaseSelector.empty')}
        </span>
      </div>
    );
  }

  return (
    <div className="database-selector" ref={containerRef} data-testid="database-selector">
      <button
        type="button"
        className="database-selector-trigger"
        onClick={() => setOpen((prev) => !prev)}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={t('databaseSelector.selectDatabase')}
        data-testid="database-selector-trigger"
      >
        <Database className="w-4 h-4 text-neon-cyan" />
        <span className="text-sm font-medium text-obsidian-100 truncate max-w-[10rem]">
          {selected?.display_name ?? t('databaseSelector.selectDatabase')}
        </span>
        <span className="database-selector-badge">
          {selected?.database_type ?? ''}
        </span>
        <ChevronDown
          className={`w-4 h-4 text-obsidian-400 transition-transform duration-200 ${
            open ? 'rotate-180' : ''
          }`}
        />
      </button>

      {open && (
        <ul
          className="database-selector-list"
          role="listbox"
          aria-label={t('databaseSelector.selectDatabase')}
          data-testid="database-selector-list"
        >
          {connections.map((conn) => (
            <li key={conn.id} role="none">
              <button
                type="button"
                role="option"
                aria-selected={conn.id === selectedId}
                className={`database-selector-item ${
                  conn.id === selectedId ? 'database-selector-item-active' : ''
                }`}
                onClick={() => handleSelect(conn.id)}
                data-testid={`database-selector-option-${conn.id}`}
              >
                <Database className="w-4 h-4 text-neon-cyan shrink-0" />
                <span className="text-sm text-obsidian-100 truncate">{conn.display_name}</span>
                <span className="database-selector-item-badge">{conn.database_type}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};
