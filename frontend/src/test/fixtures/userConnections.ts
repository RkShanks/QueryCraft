import type { UserConnectionListResponse } from '../../api/generated/types.gen';

export const E2E_USER_CONNECTIONS_RESPONSE = {
  connections: [
    {
      id: '550e8400-e29b-41d4-a716-446655440010',
      display_name: 'Local Pagila',
      database_type: 'postgresql',
    },
  ],
} satisfies UserConnectionListResponse;
