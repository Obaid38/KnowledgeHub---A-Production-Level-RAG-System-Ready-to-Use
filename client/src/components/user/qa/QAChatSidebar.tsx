"use client";

import React, { useState } from "react";
import { useTranslations } from "next-intl";
import { QAConversation } from "@/types/qa.types";
import { Can } from "@/components/auth/Can";
import Modal from "@/components/ui/modal";

interface QAChatSidebarProps {
  conversations: QAConversation[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onNewChat: () => void;
  onDelete: (id: string) => void;
}

export function QAChatSidebar({
  conversations,
  activeId,
  onSelect,
  onNewChat,
  onDelete,
}: QAChatSidebarProps) {
  const t = useTranslations("qa.sidebar");
  const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null);

  const handleDeleteClick = (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    setDeleteTargetId(id);
  };

  const handleConfirmDelete = () => {
    if (deleteTargetId) {
      onDelete(deleteTargetId);
      setDeleteTargetId(null);
    }
  };

  const handleCancelDelete = () => setDeleteTargetId(null);

  return (
    <aside className="flex h-full flex-col bg-white dark:bg-gray-900 border-r border-gray-100 dark:border-white/[0.05]">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-4 border-b border-gray-100 dark:border-white/[0.05]">
        <h2 className="text-theme-sm font-semibold text-gray-800 dark:text-white/90">
          {t("recentQueries")}
        </h2>
        <Can action="create" resource="qa">
          <button
            onClick={onNewChat}
            title={t("newChat")}
            className="flex h-8 w-8 items-center justify-center rounded-lg text-gray-400 hover:bg-gray-100 hover:text-brand-500 dark:hover:bg-white/[0.05] dark:hover:text-brand-400 transition-colors"
          >
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
          </button>
        </Can>
      </div>

      {/* Conversation list */}
      <div className="flex-1 overflow-y-auto custom-scrollbar py-2">
        {conversations.length === 0 ? (
          <p className="px-4 py-6 text-center text-theme-xs text-gray-400">
            {t("noConversations")}
          </p>
        ) : (
          <ul className="space-y-0.5 px-2">
            {conversations.map((conv) => {
              // Find the first assistant reply with a confidence score
              const firstReply = conv.messages.find(
                (m) => m.role === "assistant" && m.confidence,
              );
              return (
                <li key={conv.id}>
                  <button
                    onClick={() => onSelect(conv.id)}
                    className={`group w-full rounded-lg px-3 py-2.5 text-left transition-colors ${
                      activeId === conv.id
                        ? "bg-brand-50 dark:bg-brand-500/[0.12]"
                        : "hover:bg-gray-50 dark:hover:bg-white/[0.03]"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <p
                        className={`line-clamp-2 text-theme-xs font-medium leading-snug ${
                          activeId === conv.id
                            ? "text-brand-600 dark:text-brand-400"
                            : "text-gray-700 dark:text-gray-300"
                        }`}
                      >
                        {conv.title || conv.lastMessage}
                      </p>
                      {/* Delete — appears on hover */}
                      <Can action="delete" resource="qa">
                        <button
                          onClick={(e) => handleDeleteClick(e, conv.id)}
                          className="invisible shrink-0 rounded p-0.5 text-gray-300 hover:text-error-500 group-hover:visible dark:text-gray-600 transition-colors"
                        >
                          <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                              d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                          </svg>
                        </button>
                      </Can>
                    </div>

                    {/* Meta row */}
                    {/* <div className="mt-1 flex items-center gap-1">
                      {firstReply?.confidence && (
                        <span className="text-theme-xs text-gray-400 dark:text-gray-500">
                          {t("confidence", { value: firstReply.confidence })}
                        </span>
                      )}
                      <span className="text-theme-xs text-gray-400 dark:text-gray-500">
                        · {conv.timestamp}
                      </span>
                    </div> */}
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>
      {/* Delete confirmation modal */}
      <Modal
        isOpen={!!deleteTargetId}
        onClose={handleCancelDelete}
        showCloseButton
      >
        <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-full bg-error-50 dark:bg-error-500/10">
          <svg className="h-5 w-5 text-error-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
          </svg>
        </div>
        <h3 className="mb-1 pr-8 text-theme-sm font-semibold text-gray-800 dark:text-white/90">
          Delete conversation?
        </h3>
        <p className="mb-5 text-theme-xs text-gray-500 dark:text-gray-400">
          This conversation will be permanently deleted and cannot be recovered.
        </p>
        <div className="flex gap-3">
          <button
            onClick={handleCancelDelete}
            className="flex-1 rounded-lg border border-gray-200 bg-white py-2.5 text-theme-sm font-medium text-gray-700 hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300"
          >
            Cancel
          </button>
          <button
            onClick={handleConfirmDelete}
            className="flex-1 rounded-lg bg-error-500 py-2.5 text-theme-sm font-medium text-white hover:bg-error-600 transition-colors"
          >
            Delete
          </button>
        </div>
      </Modal>
    </aside>
  );
}