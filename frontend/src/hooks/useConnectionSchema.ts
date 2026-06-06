import { useQuery } from '@tanstack/react-query';
import { client } from '../api/generated/client.gen';

export interface ColumnSchema {
  column_name: string;
  data_type: string;
  is_primary_key: boolean;
  foreign_key: { table: string; column: string } | null;
}

export interface TableSchema {
  table_name: string;
  column_count: number;
  columns: ColumnSchema[];
}

export interface ConnectionSchema {
  connection_id: string;
  tables: TableSchema[];
  introspected_at: string | null;
}

export const useConnectionSchema = (connectionId: string | null) => {
  return useQuery<ConnectionSchema>({
    queryKey: ['connectionSchema', connectionId],
    queryFn: async () => {
      if (!connectionId) throw new Error('Connection ID is required');
      const res = await client.get({
        url: `/admin/connections/${connectionId}/schema`,
        throwOnError: true,
      });
      return res.data as ConnectionSchema;
    },
    enabled: !!connectionId,
  });
};
