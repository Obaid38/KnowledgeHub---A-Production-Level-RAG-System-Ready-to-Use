// src/services/qa.service.ts
import { privateAxios } from "@/lib/axios";
import { QAQueryRequest, QAQueryResponse, QAConversation, QAMessage, SourceDocument } from "@/types/qa.types";

// ─── Helpers ──────────────────────────────────────────────────────────────────

function formatTime(iso: string): string {
  try {
    const minsAgo = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
    if (minsAgo < 1) return "just now";
    if (minsAgo < 60) return `${minsAgo}m ago`;
    const hrs = Math.round(minsAgo / 60);
    return `${hrs}h ago`;
  } catch {
    return iso;
  }
}

// ─── Service functions ────────────────────────────────────────────────────────

/**
 * POST /qa/query — send a question and get an AI-generated answer.
 */
export async function apiQAQuery(payload: QAQueryRequest): Promise<QAQueryResponse> {
  const { data } = await privateAxios.post<QAQueryResponse>("/qa/query", {
    question:          payload.question,
    conversationId:    payload.conversationId,
    mode:              payload.mode,
    collection_filter: payload.collectionFilter,
  });
  return data;
}

/**
 * GET /qa/conversations — list the current user's conversation history.
 * Backend returns: { conversations: [{ _id, title, lastMessage, timestamp, messageCount }] }
 */
export async function apiGetConversations(): Promise<QAConversation[]> {
  const { data } = await privateAxios.get<{ conversations: Array<{
    _id:          string;
    title:        string;
    lastMessage:  string;
    timestamp:    string;
    messageCount: number;
  }> }>("/qa/conversations");

  return (data.conversations ?? []).map((c) => ({
    id:           c._id,
    title:        c.title,
    lastMessage:  c.lastMessage,
    timestamp:    formatTime(c.timestamp),
    messageCount: c.messageCount,
    messages:     [], // loaded lazily via apiGetConversation()
  }));
}

/**
 * GET /qa/conversations/:id — fetch a full conversation with all messages.
 * Backend stores messages as { userMessage, answers: [{ assistantAnswer, sources, confidence }] }.
 * We flatten each message pair into two QAMessage items (user + assistant).
 */
export async function apiGetConversation(id: string): Promise<QAConversation | null> {
  try {
    const { data } = await privateAxios.get<{
      _id:   string;
      title: string;
      messages: Array<{
        _id:         string;
        userMessage: string;
        answers:     Array<{
          assistantAnswer: string;
          sources:         SourceDocument[];
          confidence:      number;
          feedback:        "helpful" | "not_helpful" | null;
          timestamp:       string;
        }>;
        createdAt: string;
      }>;
    }>(`/qa/conversations/${id}`);

    const messages: QAMessage[] = [];

    for (const msg of data.messages ?? []) {
      // User message
      messages.push({
        id:        `${msg._id}-user`,
        role:      "user",
        content:   msg.userMessage,
        timestamp: formatTime(msg.createdAt),
      });

      // Latest assistant answer
      const answer = msg.answers?.at(-1);
      if (answer) {
        messages.push({
          id:         msg._id, // use the message _id for feedback/regenerate calls
          role:       "assistant",
          content:    answer.assistantAnswer,
          timestamp:  formatTime(answer.timestamp),
          sources:    answer.sources ?? [],
          confidence: answer.confidence ?? 0,
          feedback:   answer.feedback ?? null,
        });
      }
    }

    return {
      id:           data._id,
      title:        data.title,
      lastMessage:  messages.at(-2)?.content ?? "",
      timestamp:    "",
      messageCount: data.messages?.length ?? 0,
      messages,
    };
  } catch {
    return null;
  }
}

/** DELETE /qa/conversations/:id */
export async function apiDeleteConversation(id: string): Promise<void> {
  await privateAxios.delete(`/qa/conversations/${id}`);
}

/** POST /qa/messages/:id/feedback */
export async function apiSubmitFeedback(
  messageId: string,
  feedback: "helpful" | "not_helpful",
): Promise<void> {
  await privateAxios.post(`/qa/messages/${messageId}/feedback`, { feedback });
}

/**
 * POST /qa/messages/:id/regenerate
 * Backend returns the regenerated message in assistant format.
 */
export async function apiRegenerateAnswer(messageId: string): Promise<QAMessage> {
  const { data } = await privateAxios.post<{
    _id:        string;
    content:    string;
    timestamp:  string;
    sources:    SourceDocument[];
    confidence: number;
    feedback:   null;
  }>(`/qa/messages/${messageId}/regenerate`);

  return {
    id:         data._id,
    role:       "assistant",
    content:    data.content,
    timestamp:  formatTime(data.timestamp),
    sources:    data.sources ?? [],
    confidence: data.confidence ?? 0,
    feedback:   null,
  };
}
