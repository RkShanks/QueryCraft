import type { UserConnectionListResponse } from '../../api/generated/types.gen';

export const E2E_USER_CONNECTIONS_RESPONSE = {
  connections: [
    {
      id: 'conn-1',
      display_name: 'Local Pagila',
      database_type: 'postgresql',
    },
  ],
} satisfies UserConnectionListResponse;
