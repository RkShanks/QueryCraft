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

  // Keep ref to latest mutate to avoid effect dependency churn
  const mutateRef = useRef(mutation.mutate);
  useEffect(() => {
    mutateRef.current = mutation.mutate;
  }, [mutation.mutate]);

  // Auto-select single available connection when no selection exists.
  // This is intentional prop-to-state synchronization.
  useEffect(() => {
    if (selectedConnectionId === null && availableConnections.length === 1) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setSelectedConnectionIdState(availableConnections[0].id);
    }
  }, [selectedConnectionId, availableConnections]);

  // Trigger PATCH when selection changes and a session id exists.
  const prevSelectedRef = useRef<string | null>(selectedConnectionId);
  useEffect(() => {
    if (prevSelectedRef.current !== selectedConnectionId) {
      prevSelectedRef.current = selectedConnectionId;
      if (sessionId && selectedConnectionId) {
        mutateRef.current(selectedConnectionId);
      }
    }
  }, [sessionId, selectedConnectionId]);

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

  return {
    selectedConnectionId,
    setSelectedConnectionId,
    isLoading: mutation.isPending,
    isError: mutation.isError,
    error: mutation.error as Error | null,
  };
};
