import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Plus, X } from 'lucide-react';

interface GroupMappingEditorProps {
  groups: string[];
  onChange: (groups: string[]) => void;
}

export const GroupMappingEditor: React.FC<GroupMappingEditorProps> = ({ groups, onChange }) => {
  const { t } = useTranslation();
  const [newGroup, setNewGroup] = useState('');

  const handleAdd = (e: React.MouseEvent) => {
    e.preventDefault();
    const trimmed = newGroup.trim();
    if (trimmed && !groups.includes(trimmed)) {
      onChange([...groups, trimmed]);
      setNewGroup('');
    }
  };

  const handleRemove = (e: React.MouseEvent, groupToRemove: string) => {
    e.preventDefault();
    onChange(groups.filter((g) => g !== groupToRemove));
  };

  return (
    <div className="space-y-3" data-testid="group-mapping-editor">
      <label className="block text-sm font-medium text-gray-400">
        {t('admin.roles.form.groupMappings') || 'SSO Group Mappings'}
      </label>

      <div className="flex gap-2">
        <input
          type="text"
          value={newGroup}
          onChange={(e) => setNewGroup(e.target.value)}
          placeholder={t('admin.roles.form.groupMappingPlaceholder') || 'Enter SSO group value'}
          className="flex-1 bg-gray-950 border border-gray-800 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-neon-cyan transition-colors"
        />
        <button
          type="button"
          onClick={handleAdd}
          className="flex items-center justify-center px-4 py-2 bg-neon-cyan text-gray-900 font-semibold rounded-lg hover:bg-opacity-90 transition-colors"
        >
          <Plus className="w-4 h-4 me-1" />
          {t('common.add')}
        </button>
      </div>

      <div className="flex flex-wrap gap-2 pt-1">
        {groups.length === 0 ? (
          <span className="text-sm text-gray-500 italic">
            {t('admin.roles.form.noGroupMappings') || 'No SSO groups mapped.'}
          </span>
        ) : (
          groups.map((group) => (
            <span
              key={group}
              className="inline-flex items-center gap-1 px-3 py-1 bg-gray-800 border border-gray-700 text-neon-cyan text-sm font-medium rounded-full"
            >
              {group}
              <button
                type="button"
                onClick={(e) => handleRemove(e, group)}
                className="text-gray-400 hover:text-red-400 p-0.5 rounded-full hover:bg-gray-700 transition-colors"
                aria-label={`${t('common.remove')} ${group}`}
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </span>
          ))
        )}
      </div>
    </div>
  );
};
