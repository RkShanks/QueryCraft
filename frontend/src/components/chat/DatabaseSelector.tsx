import React, { useState, useRef, useEffect, useCallback, useId } from 'react';
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

const TYPEAHEAD_RESET_MS = 500;

export const DatabaseSelector: React.FC<DatabaseSelectorProps> = ({
  connections,
  selectedId,
  onSelect,
}) => {
  const { t, i18n } = useTranslation();
  const [open, setOpen] = useState(false);
  const [focusedId, setFocusedId] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const listRef = useRef<HTMLUListElement>(null);
  const typeaheadRef = useRef({ text: '', time: 0 });
  const autoSelectedRef = useRef<string | null>(null);
  const listboxId = useId();

  const locale = i18n.language || 'en';
  const selected = connections.find((c) => c.id === selectedId);

  // Auto-select single connection without stealing focus or duplicating callbacks.
  useEffect(() => {
    if (connections.length === 1 && !selectedId && autoSelectedRef.current !== connections[0].id) {
      autoSelectedRef.current = connections[0].id;
      onSelect(connections[0].id);
    }
  }, [connections, selectedId, onSelect]);

  const focusOption = useCallback((id: string | null) => {
    if (!id || !listRef.current) return;
    const element = listRef.current.querySelector<HTMLElement>(`[data-option-id="${id}"]`);
    element?.focus();
  }, []);

  // Move DOM focus whenever the active option changes while open.
  useEffect(() => {
    if (open) focusOption(focusedId);
  }, [open, focusedId, focusOption]);

  const openListbox = useCallback(() => {
    const target =
      connections.find((c) => c.id === selectedId)?.id ?? connections[0]?.id ?? null;
    setFocusedId(target);
    setOpen(true);
  }, [connections, selectedId]);

  // Keep active focus coherent when the connection list changes while open.
  useEffect(() => {
    if (!open) return;
    setFocusedId((current) => {
      if (current && connections.some((c) => c.id === current)) return current;
      return (
        connections.find((c) => c.id === selectedId)?.id ?? connections[0]?.id ?? null
      );
    });
  }, [open, connections, selectedId]);

  // Close on outside click.
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
      triggerRef.current?.focus();
    },
    [onSelect]
  );

  const closeListbox = useCallback((restoreTriggerFocus: boolean) => {
    setOpen(false);
    typeaheadRef.current = { text: '', time: 0 };
    if (restoreTriggerFocus) triggerRef.current?.focus();
  }, []);

  const moveActive = useCallback(
    (nextIndex: number) => {
      if (connections.length === 0) return;
      const clamped = Math.min(Math.max(nextIndex, 0), connections.length - 1);
      setFocusedId(connections[clamped].id);
    },
    [connections]
  );

  const handleTypeahead = useCallback(
    (key: string) => {
      if (connections.length === 0) return;
      const now = Date.now();
      const buffer =
        now - typeaheadRef.current.time <= TYPEAHEAD_RESET_MS
          ? typeaheadRef.current.text + key
          : key;
      typeaheadRef.current = { text: buffer, time: now };

      const query = buffer.toLocaleLowerCase(locale);
      const currentIndex = Math.max(
        connections.findIndex((c) => c.id === focusedId),
        -1
      );
      const queries = query === key.toLocaleLowerCase(locale)
        ? [query]
        : [query, key.toLocaleLowerCase(locale)];
      for (const candidate of queries) {
        for (let step = 1; step <= connections.length; step += 1) {
          const index = (currentIndex + step) % connections.length;
          if (
            connections[index].display_name.toLocaleLowerCase(locale).startsWith(candidate)
          ) {
            setFocusedId(connections[index].id);
            return;
          }
        }
      }
    },
    [connections, focusedId, locale]
  );

  const handleListKeyDown = useCallback(
    (event: React.KeyboardEvent<HTMLUListElement>) => {
      const currentIndex = connections.findIndex((c) => c.id === focusedId);
      switch (event.key) {
        case 'ArrowDown':
          event.preventDefault();
          moveActive(currentIndex < 0 ? 0 : currentIndex + 1);
          break;
        case 'ArrowUp':
          event.preventDefault();
          moveActive(currentIndex < 0 ? 0 : currentIndex - 1);
          break;
        case 'Home':
          event.preventDefault();
          moveActive(0);
          break;
        case 'End':
          event.preventDefault();
          moveActive(connections.length - 1);
          break;
        case 'Enter':
        case ' ':
          event.preventDefault();
          if (focusedId) handleSelect(focusedId);
          break;
        case 'Escape':
          event.preventDefault();
          closeListbox(true);
          break;
        case 'Tab':
          closeListbox(false);
          break;
        default:
          if (event.key.length === 1 && !event.altKey && !event.ctrlKey && !event.metaKey) {
            handleTypeahead(event.key);
          }
          break;
      }
    },
    [
      connections,
      focusedId,
      moveActive,
      handleSelect,
      closeListbox,
      handleTypeahead,
    ]
  );

  const handleTriggerKeyDown = useCallback(
    (event: React.KeyboardEvent<HTMLButtonElement>) => {
      if (!open) {
        if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
          event.preventDefault();
          openListbox();
        }
        return;
      }
      if (event.key === 'Escape') {
        event.preventDefault();
        closeListbox(true);
      }
    },
    [open, openListbox, closeListbox]
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
        ref={triggerRef}
        className="database-selector-trigger"
        onClick={() => (open ? setOpen(false) : openListbox())}
        onKeyDown={handleTriggerKeyDown}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={open ? listboxId : undefined}
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
          ref={listRef}
          id={listboxId}
          className="database-selector-list"
          role="listbox"
          aria-label={t('databaseSelector.selectDatabase')}
          onKeyDown={handleListKeyDown}
          data-testid="database-selector-list"
        >
          {connections.map((conn) => (
            <li
              key={conn.id}
              role="option"
              tabIndex={-1}
              data-option-id={conn.id}
              aria-selected={conn.id === selectedId}
              className={`database-selector-item ${
                conn.id === selectedId ? 'database-selector-item-active' : ''
              } ${conn.id === focusedId ? 'database-selector-item-focused' : ''}`}
              onClick={() => handleSelect(conn.id)}
              data-testid={`database-selector-option-${conn.id}`}
            >
              <Database className="w-4 h-4 text-neon-cyan shrink-0" />
              <span className="text-sm text-obsidian-100 truncate">{conn.display_name}</span>
              <span className="database-selector-item-badge">{conn.database_type}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};
