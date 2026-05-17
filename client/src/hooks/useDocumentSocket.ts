// src/hooks/useDocumentSocket.ts
// Listens for real-time document status events and patches the React Query cache
// so the table updates immediately without a page refresh.
"use client";

import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "react-toastify";
import { getSocket } from "@/lib/socket";
import { DOCS_KEY } from "@/hooks/queries/useDocumentsQuery";
import { Document, DocumentStatus } from "@/types/documents";

interface DocumentStatusEvent {
  id:     string;
  status: DocumentStatus;
}

/**
 * Mount this hook inside any component that shows the document table.
 * It opens a WebSocket connection on mount, patches the cache on every
 * `document:status` event, and cleans up the listener on unmount.
 *
 * @param onSettled - called with the document id whenever processing ends
 *   (status becomes Completed or Failed), so callers can clear local state.
 */
export function useDocumentSocket(onSettled?: (id: string) => void) {
  const qc = useQueryClient();

  useEffect(() => {
    const socket = getSocket();

    if (!socket.connected) socket.connect();

    function onStatus({ id, status }: DocumentStatusEvent) {
      // Patch every cached variant of the documents query in place —
      // avoids a network round-trip while keeping the table up to date.
      qc.setQueriesData<{ documents: Document[]; pagination: unknown }>(
        { queryKey: DOCS_KEY },
        (old) => {
          if (!old) return old;
          return {
            ...old,
            documents: old.documents.map((doc) =>
              doc.id === id ? { ...doc, status } : doc,
            ),
          };
        },
      );

      if (status === "Completed") {
        toast.success("Document processing completed.", { autoClose: false, closeOnClick: true });
        onSettled?.(id);
      } else if (status === "Failed") {
        toast.error("Document processing failed.");
        onSettled?.(id);
      }
    }

    socket.on("document:status", onStatus);

    return () => {
      socket.off("document:status", onStatus);
    };
  // onSettled is intentionally excluded — it's a callback ref that changes
  // on every render; re-registering the socket listener for it would cause flicker.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [qc]);
}
