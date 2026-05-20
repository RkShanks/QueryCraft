import { useState, useEffect, useCallback, useRef } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { updateSessionConnection } from '../api/generated/sdk.gen';
import type { UserConnectionResponse } from '../api/generated/types.gen';

export interface UseConnectionSelectionOptions {
  sessionId: string | null;
  initialConnectionId: string | null;
  availableConnections: UserConnectionResponse[];
}

export interface UseConnectionSelectionReturn {
  selectedConnectionId: string | null;
  setSelectedConnectionId: (id: string | null) => void;
  isLoading: boolean;
  isError: boolean;
  error: Error | null;
}

export const useConnectionSelection = ({
  sessionId,
  initialConnectionId,
  availableConnections,
}: UseConnectionSelectionOptions): UseConnectionSelectionReturn => {
  const [selectedConnectionId, setSelectedConnectionIdState] = useState<string | null>(
    initialConnectionId
  );
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: (connectionId: string) =>
      sessionId
        ? updateSessionConnection({
            path: { sessionId },
            body: { connection_id: connectionId },
            throwOnError: true,
          }).then((res) => res.data)
        : Promise.resolve(null),
    onSuccess: () => {
      if (sessionId) {
        queryClient.invalidateQueries({ queryKey: ['sessions', sessionId] });
      }
    },
  });

  // Keep a stable ref to the latest mutate function to avoid effect dependency churn
  const mutateRef = useRef(mutation.mutate);
  mutateRef.current = mutation.mutate;

  // Auto-select single available connection when no selection exists
  useEffect(() => {
    if (selectedConnectionId === null && availableConnections.length === 1) {
      setSelectedConnectionIdState(availableConnections[0].id);
    }
  }, [selectedConnectionId, availableConnections]);

  const setSelectedConnectionId = useCallback(
    (id: string | null) => {
      setSelectedConnectionIdState((prev) => {
        if (prev === id) {
          return prev;
        }
        return id;
      });
    },
    []
  );

  // Trigger PATCH when selection changes and session exists
  useEffect(() => {
    if (sessionId && selectedConnectionId) {
      mutateRef.current(selectedConnectionId);
    }
  }, [sessionId, selectedConnectionId]);

  return {
    selectedConnectionId,
    setSelectedConnectionId,
    isLoading: mutation.isPending,
    isError: mutation.isError,
    error: mutation.error as Error | null,
  };
};
