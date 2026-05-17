import { RouterStatus } from "../types/qa.types";

// ── Router status config ───────────────────────────────────────────────────
// label keys map to qa.router.* in the locale files
export const ROUTER_STATUSES: RouterStatus[] = [
  { mode: "rag",    label: "ragMode",      active: true  },
  { mode: "hybrid", label: "hybridRouter", active: true  },
  { mode: "direct", label: "directMode",   active: false },
];

