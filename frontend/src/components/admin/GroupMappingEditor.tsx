import React from 'react';

interface GroupMappingEditorProps {
  groups: string[];
  onChange: (groups: string[]) => void;
}

export const GroupMappingEditor: React.FC<GroupMappingEditorProps> = () => {
  return <div data-testid="group-mapping-editor">Group Mapping Editor Stub</div>;
};
