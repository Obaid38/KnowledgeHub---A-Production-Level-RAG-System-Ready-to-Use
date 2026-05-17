"use client";

import React, { useState, useRef, useEffect } from "react";
import { useTranslations } from "next-intl";
import { useRouter, usePathname, useSearchParams } from "next/navigation";
import { toast } from "react-toastify";
import { QAConversation, QAMessage, QAMode } from "@/types/qa.types";
import {
  useConversationsQuery,
  useDeleteConversationMutation,
  useQAQueryMutation,
  useSubmitFeedbackMutation,
  useRegenerateAnswerMutation,
} from "@/hooks/queries/useQAQuery";
import { apiGetConversation } from "@/services/qa.service";
import { QAChatSidebar } from "@/components/user/qa/QAChatSidebar";
import { QAMessageBubble } from "@/components/user/qa/QAMessageBubble";
import { QAEmptyState } from "@/components/user/qa/QAEmptyState";
import { QAInputBar } from "@/components/user/qa/QAInputBar";
import { RouterStatusBadges } from "@/components/user/qa/RouterStatusBadge";
import { Can } from "@/components/auth/Can";

const MOBILE_BREAKPOINT = 1024;

export default function QAEngine() {
  const t     = useTranslations("qa");
  const tChat = useTranslations("qa.chat");

  // ── URL sync ───────────────────────────────────────────────────────────────
  const router       = useRouter();
  const pathname     = usePathname();
  const searchParams = useSearchParams();

  const setConvUrl = (id: string | null) => {
    if (id) {
      router.replace(`${pathname}?id=${id}`, { scroll: false });
    } else {
      router.replace(pathname, { scroll: false });
    }
  };

  // ── Responsive sidebar ─────────────────────────────────────────────────────
  const [isMobile,    setIsMobile]    = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);

  useEffect(() => {
    const check = () => {
      const mobile = window.innerWidth < MOBILE_BREAKPOINT;
      setIsMobile(mobile);
      setSidebarOpen(!mobile);
    };
    check();
    window.addEventListener("resize", check);
    return () => window.removeEventListener("resize", check);
  }, []);

  // ── Conversations from server ──────────────────────────────────────────────
  const { data: serverConversations = [] } = useConversationsQuery();

  // Local state holds the full conversations (with messages) for the active session.
  // We start with the server list (messages: []) and hydrate on selection.
  const [localConvs,   setLocalConvs]   = useState<QAConversation[]>([]);
  const [activeConvId, setActiveConvId] = useState<string | null>(null);

  // Messages shown while a brand-new conversation is in-flight (no sidebar entry yet).
  const [pendingMessages, setPendingMessages] = useState<QAMessage[]>([]);

  // Tracks whether we've already restored the conversation from the URL on first load.
  const hasRestoredRef = useRef(false);

  // Sync server list into local state without overwriting loaded messages.
  // On the very first load, also restore the conversation from ?id= if present.
  useEffect(() => {
    setLocalConvs((prev) => {
      const prevMap = new Map(prev.map((c) => [c.id, c]));
      return serverConversations.map((sc) => {
        const local = prevMap.get(sc.id);
        if (!local) return sc;
        // Always take title/metadata from server; keep locally-loaded messages
        return { ...local, title: sc.title, lastMessage: sc.lastMessage, timestamp: sc.timestamp, messageCount: sc.messageCount };
      });
    });

    if (!hasRestoredRef.current && serverConversations.length > 0) {
      hasRestoredRef.current = true;
      const urlId = searchParams.get("id");
      if (urlId && serverConversations.some((c) => c.id === urlId)) {
        setActiveConvId(urlId);
        apiGetConversation(urlId).then((full) => {
          if (full) {
            setLocalConvs((prev) =>
              prev.map((c) => (c.id === urlId ? { ...c, messages: full.messages } : c)),
            );
          }
        });
      }
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [serverConversations]);

  const activeConv = localConvs.find((c) => c.id === activeConvId) ?? null;

  // Messages to render: active conversation OR the in-flight pending messages
  const displayMessages = activeConv ? activeConv.messages : pendingMessages;

  // ── Query state ────────────────────────────────────────────────────────────
  const [input,              setInput]              = useState("");
  const [mode]                                      = useState<QAMode>("rag");
  const [collectionFilter,   setCollectionFilter]   = useState<string[]>([]);

  const bottomRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [displayMessages]);

  // ── Mutations ──────────────────────────────────────────────────────────────
  const deleteMutation     = useDeleteConversationMutation();
  const queryMutation      = useQAQueryMutation();
  const feedbackMutation   = useSubmitFeedbackMutation();
  const regenerateMutation = useRegenerateAnswerMutation();

  // ── Helpers ────────────────────────────────────────────────────────────────
  const closeSidebarOnMobile = () => { if (isMobile) setSidebarOpen(false); };

  const handleNewChat = () => {
    setActiveConvId(null);
    setPendingMessages([]);
    setInput("");
    setConvUrl(null);
    closeSidebarOnMobile();
  };

  const handleSelectConv = async (id: string) => {
    setActiveConvId(id);
    setPendingMessages([]);
    setConvUrl(id);
    closeSidebarOnMobile();

    // Lazy-load full messages for this conversation if not yet fetched
    const existing = localConvs.find((c) => c.id === id);
    if (!existing || existing.messages.length === 0) {
      const full = await apiGetConversation(id);
      if (full) {
        setLocalConvs((prev) =>
          prev.map((c) => (c.id === id ? { ...c, messages: full.messages } : c)),
        );
      }
    }
  };

  const handleDeleteConv = (id: string) => {
    deleteMutation.mutate(id, {
      onSuccess: () => {
        setLocalConvs((prev) => prev.filter((c) => c.id !== id));
        if (activeConvId === id) {
          setActiveConvId(null);
          setPendingMessages([]);
          setConvUrl(null);
        }
        toast.success("Conversation deleted");
      },
      onError: (err: unknown) => {
        const message = err instanceof Error ? err.message : "Failed to delete conversation";
        toast.error(message);
      },
    });
  };

  const handleSubmit = async () => {
    const question = input.trim();
    if (!question || queryMutation.isPending) return;

    setInput("");

    const userMsg: QAMessage = {
      id:        `user-${Date.now()}`,
      role:      "user",
      content:   question,
      timestamp: tChat("justNow"),
    };

    const streamingMsg: QAMessage = {
      id:          `stream-${Date.now()}`,
      role:        "assistant",
      content:     "",
      timestamp:   tChat("justNow"),
      isStreaming: true,
    };

    const convId = activeConvId;

    if (!convId) {
      // No active conversation yet — show messages in the pending area only.
      // The sidebar entry is created after the server responds with a real id.
      setPendingMessages([userMsg, streamingMsg]);
    } else {
      setLocalConvs((prev) =>
        prev.map((c) =>
          c.id === convId
            ? { ...c, messages: [...c.messages, userMsg, streamingMsg], lastMessage: question }
            : c,
        ),
      );
    }

    queryMutation.mutate(
      { question, conversationId: convId ?? undefined, mode, collectionFilter },
      {
        onSuccess: (response) => {
          const assistantMsg: QAMessage = {
            id:         response.messageId,
            role:       "assistant",
            content:    response.answer,
            timestamp:  tChat("justNow"),
            sources:    response.sources,
            confidence: response.confidence,
            feedback:   null,
          };

          if (!convId) {
            // New conversation: add it to the sidebar with the real server id.
            // The title will be refreshed from the server once CONV_KEY invalidation
            // triggers a refetch (via useQAQueryMutation's onSuccess).
            const newConv: QAConversation = {
              id:           response.conversationId,
              title:        question.slice(0, 60),
              lastMessage:  question,
              timestamp:    tChat("justNow"),
              messageCount: 1,
              messages:     [userMsg, assistantMsg],
            };
            setLocalConvs((prev) => [newConv, ...prev]);
            setActiveConvId(response.conversationId);
            setPendingMessages([]);
            setConvUrl(response.conversationId);
          } else {
            setLocalConvs((prev) =>
              prev.map((c) => {
                if (c.id !== convId) return c;
                return {
                  ...c,
                  messages: [...c.messages.filter((m) => !m.isStreaming), assistantMsg],
                };
              }),
            );
          }
        },
        onError: (err: unknown) => {
          const message = err instanceof Error ? err.message : "Failed to get an answer";
          toast.error(message);

          if (!convId) {
            // Remove the pending messages — nothing to keep without a real conv
            setPendingMessages([]);
          } else {
            setLocalConvs((prev) =>
              prev.map((c) =>
                c.id === convId
                  ? { ...c, messages: c.messages.filter((m) => !m.isStreaming) }
                  : c,
              ),
            );
          }
        },
      },
    );
  };

  const handleFeedback = (messageId: string, feedback: "helpful" | "not_helpful") => {
    feedbackMutation.mutate(
      { messageId, feedback },
      {
        onSuccess: () => {
          setLocalConvs((prev) =>
            prev.map((c) => ({
              ...c,
              messages: c.messages.map((m) => (m.id === messageId ? { ...m, feedback } : m)),
            })),
          );
        },
        onError: (err: unknown) => {
          const message = err instanceof Error ? err.message : "Failed to submit feedback";
          toast.error(message);
        },
      },
    );
  };

  const handleRegenerate = (messageId: string) => {
    regenerateMutation.mutate(messageId, {
      onSuccess: (updated) => {
        setLocalConvs((prev) =>
          prev.map((c) => ({
            ...c,
            messages: c.messages.map((m) => (m.id === messageId ? updated : m)),
          })),
        );
      },
      onError: (err: unknown) => {
        const message = err instanceof Error ? err.message : "Failed to regenerate answer";
        toast.error(message);
      },
    });
  };

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div className="space-y-6">
      <div>
        <h1>{t("title")}</h1>
        <p>{t("subtitle")}</p>
      </div>

      <div
        className="relative flex overflow-hidden rounded-xl border border-gray-200 bg-white dark:border-white/[0.05] dark:bg-white/[0.03]"
        style={{ height: "calc(100vh - 220px)", minHeight: "520px" }}
      >
        {isMobile && sidebarOpen && (
          <div
            className="absolute inset-0 z-20 bg-black/30 backdrop-blur-sm"
            onClick={() => setSidebarOpen(false)}
          />
        )}

        {/* Sidebar */}
        <div
          className={
            isMobile
              ? `absolute inset-y-0 left-0 z-30 w-72 transform shadow-theme-xl transition-transform duration-200 ease-in-out ${sidebarOpen ? "translate-x-0" : "-translate-x-full"}`
              : `relative flex-shrink-0 overflow-hidden transition-all duration-200 ease-in-out ${sidebarOpen ? "w-72" : "w-0"}`
          }
        >
          <div className="h-full w-72">
            <QAChatSidebar
              conversations={localConvs}
              activeId={activeConvId}
              onSelect={handleSelectConv}
              onNewChat={handleNewChat}
              onDelete={handleDeleteConv}
            />
          </div>
        </div>

        {/* Chat area */}
        <div className="flex min-w-0 flex-1 flex-col">
          <div className="flex items-center gap-3 border-b border-gray-100 px-4 py-3 dark:border-white/[0.05]">
            <button
              onClick={() => setSidebarOpen((o) => !o)}
              className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-gray-500 hover:bg-gray-100 hover:text-gray-700 dark:hover:bg-white/[0.05] dark:hover:text-gray-300 transition-colors"
              title={sidebarOpen ? "Hide history" : "Show history"}
            >
              <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d={sidebarOpen ? "M11 19l-7-7 7-7m8 14l-7-7 7-7" : "M4 6h16M4 12h16M4 18h16"}
                />
              </svg>
            </button>

            <div className="flex min-w-0 flex-1 items-center justify-between gap-3">
              <h2 className="truncate">
                {activeConv
                  ? activeConv.title
                  : pendingMessages.length > 0
                    ? tChat("justNow")
                    : tChat("askQuestion")}
              </h2>
              <RouterStatusBadges mode={mode} />
            </div>
          </div>

          <div className="flex-1 overflow-y-auto custom-scrollbar px-4 py-5">
            {displayMessages.length === 0 ? (
              <QAEmptyState onPromptSelect={(p) => setInput(p)} />
            ) : (
              <div className="mx-auto max-w-3xl space-y-5">
                {displayMessages.map((msg) => (
                  <QAMessageBubble
                    key={msg.id}
                    message={msg}
                    onFeedback={handleFeedback}
                    onRegenerate={handleRegenerate}
                  />
                ))}
                <div ref={bottomRef} />
              </div>
            )}
          </div>

          <Can
            action="create"
            resource="qa"
            fallback={
              <div className="border-t border-gray-100 px-4 py-3 dark:border-white/[0.05]">
                <p className="text-center text-theme-sm text-gray-400 dark:text-gray-500">
                  You don&apos;t have permission to submit queries.
                </p>
              </div>
            }
          >
            <QAInputBar
              value={input}
              onChange={setInput}
              onSubmit={handleSubmit}
              loading={queryMutation.isPending}
              selectedCategories={collectionFilter}
              onCategoriesChange={setCollectionFilter}
            />
          </Can>
        </div>
      </div>
    </div>
  );
}
