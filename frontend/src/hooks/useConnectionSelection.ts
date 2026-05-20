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

  // Track whether the user has explicitly made a selection.
  // User selection takes precedence over prop-driven sync.
  const userSelectedRef = useRef(false);

  // Track whether the next selection change was driven by prop sync
  // (initialConnectionId arriving later) so we can skip PATCH.
  const skipNextPatchRef = useRef(false);

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

  // Sync initialConnectionId prop to state when it arrives or changes,
  // unless the user has already made an explicit selection.
  useEffect(() => {
    if (!userSelectedRef.current && initialConnectionId !== null) {
      setSelectedConnectionIdState((prev) => {
        if (prev === initialConnectionId) return prev;
        skipNextPatchRef.current = true;
        return initialConnectionId;
      });
    }
  }, [initialConnectionId]);

  // Auto-select single available connection when no selection exists
  // and no initialConnectionId has been provided.
  useEffect(() => {
    if (
      !userSelectedRef.current &&
      selectedConnectionId === null &&
      initialConnectionId === null &&
      availableConnections.length === 1
    ) {
      skipNextPatchRef.current = true;
      setSelectedConnectionIdState(availableConnections[0].id);
    }
  }, [selectedConnectionId, initialConnectionId, availableConnections]);

  // Trigger PATCH when selection changes and a session id exists.
  const prevSelectedRef = useRef<string | null>(selectedConnectionId);
  useEffect(() => {
    if (prevSelectedRef.current !== selectedConnectionId) {
      prevSelectedRef.current = selectedConnectionId;
      if (sessionId && selectedConnectionId) {
        if (skipNextPatchRef.current) {
          skipNextPatchRef.current = false;
        } else {
          mutateRef.current(selectedConnectionId);
        }
      }
    }
  }, [sessionId, selectedConnectionId]);

  const setSelectedConnectionId = useCallback(
    (id: string | null) => {
      userSelectedRef.current = true;
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
