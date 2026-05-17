"use client";

import { useState, useEffect } from "react";

const THINKING_PHASES = [
  { label: "Thinking…",            icon: "💭" },
  { label: "Searching documents…", icon: "🔍" },
  { label: "Generating response…", icon: "✍️" },
];

export function ThinkingIndicator() {
  const [phase, setPhase] = useState(0);

  useEffect(() => {
    if (phase >= THINKING_PHASES.length - 1) return;

    const id = setTimeout(() => {
      setPhase((p) => p + 1);
    }, 5000);

    return () => clearTimeout(id);
  }, [phase]);

  const current = THINKING_PHASES[phase];

  return (
    <div className="flex items-center gap-3 py-2">
      {/* Bouncing dots */}
      <div className="flex gap-1">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="h-2 w-2 rounded-full bg-brand-400 animate-bounce"
            style={{ animationDelay: `${i * 0.15}s` }}
          />
        ))}
      </div>

      {/* Phase label — fades between states */}
      <span className="text-theme-xs text-gray-400 transition-all duration-300">
        {current.icon} {current.label}
      </span>
    </div>
  );
}