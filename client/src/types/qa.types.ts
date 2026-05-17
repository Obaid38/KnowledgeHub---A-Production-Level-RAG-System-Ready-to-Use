// ── Message types ──────────────────────────────────────────────────────────
export type MessageRole = "user" | "assistant";

export interface SourceDocument {
  id: string;
  filename: string;
  type: string;
  page?: number;
}

export interface QAMessage {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: string;
  sources?: SourceDocument[];
  confidence?: number;
  isStreaming?: boolean;
  feedback?: "helpful" | "not_helpful" | null;
}

// ── Conversation / session types ───────────────────────────────────────────
export interface QAConversation {
  id: string;
  title: string;
  lastMessage: string;
  timestamp: string;
  messageCount: number;
  messages: QAMessage[];
}

// ── Query request / response (mirrors what the API will expect) ────────────
export interface QAQueryRequest {
  question: string;
  conversationId?: string;
  mode?: QAMode;
  collectionFilter?: string[];
}

export interface QAQueryResponse {
  answer: string;
  sources: SourceDocument[];
  confidence: number;
  conversationId: string;
  messageId: string;
}

// ── UI enums ───────────────────────────────────────────────────────────────
export type QAMode = "rag" | "hybrid" | "direct";

export interface RouterStatus {
  mode: QAMode;
  label: string;
  active: boolean;
}