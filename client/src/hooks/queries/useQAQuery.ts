// src/hooks/queries/useQAQuery.ts
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  apiGetConversations,
  apiGetConversation,
  apiDeleteConversation,
  apiQAQuery,
  apiSubmitFeedback,
  apiRegenerateAnswer,
} from "@/services/qa.service";
import { QAQueryRequest } from "@/types/qa.types";

export const CONV_KEY = ["qa", "conversations"] as const;

/** List all conversations for the current user. */
export function useConversationsQuery() {
  return useQuery({
    queryKey: CONV_KEY,
    queryFn:  apiGetConversations,
    staleTime: 30 * 1000,
  });
}

/** Fetch a full conversation (with messages) by ID. */
export function useConversationQuery(id: string | null) {
  return useQuery({
    queryKey: [...CONV_KEY, id],
    queryFn:  () => apiGetConversation(id!),
    enabled:  !!id,
    staleTime: 30 * 1000,
  });
}

/** Delete a conversation — refreshes the list. */
export function useDeleteConversationMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: apiDeleteConversation,
    onSuccess:  () => qc.invalidateQueries({ queryKey: CONV_KEY }),
  });
}

/** Submit a question to the AI — refreshes the conversation list on success. */
export function useQAQueryMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: QAQueryRequest) => apiQAQuery(payload),
    onSuccess:  () => qc.invalidateQueries({ queryKey: CONV_KEY }),
  });
}

/** Submit helpful / not_helpful feedback on a message. */
export function useSubmitFeedbackMutation() {
  return useMutation({
    mutationFn: ({ messageId, feedback }: { messageId: string; feedback: "helpful" | "not_helpful" }) =>
      apiSubmitFeedback(messageId, feedback),
  });
}

/** Regenerate the AI answer for a given message. */
export function useRegenerateAnswerMutation() {
  return useMutation({
    mutationFn: (messageId: string) => apiRegenerateAnswer(messageId),
  });
}
