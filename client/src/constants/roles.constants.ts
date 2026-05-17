import { RolePermissions } from "@/types/roles.types";

// ── Static tab definitions for the 4 system roles ────────────────────────────
// Dynamic / custom roles are fetched from the API and appended at runtime.
export const SYSTEM_ROLE_TABS: { role: string; label: string; hint: string; isSystem: boolean }[] = [
  { role: "admin",   label: "Admin",   hint: "80+ permissions", isSystem: true },
  { role: "manager", label: "Manager", hint: "60+ permissions", isSystem: true },
  { role: "user",    label: "User",    hint: "15+ permissions", isSystem: true },
  { role: "viewer",  label: "Viewer",  hint: "Read-only",       isSystem: true },
];

// ── Default permission matrix per role (PDF-aligned) ─────────────────────────
// Categories: Document, Email, Q&A, Knowledge Graph, NLU, SAP, Admin, Backup, System
export const DEFAULT_ROLE_PERMISSIONS: RolePermissions[] = [
  {
    role:  "admin",
    label: "Admin",
    permissions: [
      { id: "document",        category: "Document",        view: true,  create: true,  edit: true,  delete: true  },
      { id: "email",           category: "Email",           view: true,  create: true,  edit: true,  delete: true  },
      { id: "qa",              category: "Q&A",             view: true,  create: true,  edit: true,  delete: true  },
      { id: "knowledge-graph", category: "Knowledge Graph", view: true,  create: true,  edit: true,  delete: true  },
      { id: "nlu",             category: "NLU",             view: true,  create: true,  edit: true,  delete: true  },
      { id: "sap",             category: "SAP",             view: true,  create: true,  edit: true,  delete: true  },
      { id: "admin",           category: "Admin",           view: true,  create: true,  edit: true,  delete: true  },
      { id: "backup",          category: "Backup",          view: true,  create: true,  edit: true,  delete: true  },
      { id: "system",          category: "System",          view: true,  create: true,  edit: true,  delete: true  },
    ],
  },
  {
    role:  "manager",
    label: "Manager",
    permissions: [
      { id: "document",        category: "Document",        view: true,  create: true,  edit: true,  delete: true  },
      { id: "email",           category: "Email",           view: true,  create: true,  edit: true,  delete: true  },
      { id: "qa",              category: "Q&A",             view: true,  create: true,  edit: true,  delete: true  },
      { id: "knowledge-graph", category: "Knowledge Graph", view: true,  create: true,  edit: true,  delete: true  },
      { id: "nlu",             category: "NLU",             view: true,  create: true,  edit: true,  delete: false },
      { id: "sap",             category: "SAP",             view: true,  create: true,  edit: true,  delete: true  },
      { id: "admin",           category: "Admin",           view: false, create: false, edit: false, delete: false },
      { id: "backup",          category: "Backup",          view: false, create: false, edit: false, delete: false },
      { id: "system",          category: "System",          view: false, create: false, edit: false, delete: false },
    ],
  },
  {
    role:  "user",
    label: "User",
    permissions: [
      { id: "document",        category: "Document",        view: true,  create: true,  edit: true,  delete: false },
      { id: "email",           category: "Email",           view: true,  create: false, edit: false, delete: false },
      { id: "qa",              category: "Q&A",             view: true,  create: true,  edit: false, delete: false },
      { id: "knowledge-graph", category: "Knowledge Graph", view: true,  create: false, edit: false, delete: false },
      { id: "nlu",             category: "NLU",             view: false, create: false, edit: false, delete: false },
      { id: "sap",             category: "SAP",             view: true,  create: false, edit: false, delete: false },
      { id: "admin",           category: "Admin",           view: false, create: false, edit: false, delete: false },
      { id: "backup",          category: "Backup",          view: false, create: false, edit: false, delete: false },
      { id: "system",          category: "System",          view: false, create: false, edit: false, delete: false },
    ],
  },
  {
    role:  "viewer",
    label: "Viewer",
    permissions: [
      { id: "document",        category: "Document",        view: true,  create: false, edit: false, delete: false },
      { id: "email",           category: "Email",           view: false, create: false, edit: false, delete: false },
      { id: "qa",              category: "Q&A",             view: true,  create: false, edit: false, delete: false },
      { id: "knowledge-graph", category: "Knowledge Graph", view: true,  create: false, edit: false, delete: false },
      { id: "nlu",             category: "NLU",             view: false, create: false, edit: false, delete: false },
      { id: "sap",             category: "SAP",             view: false, create: false, edit: false, delete: false },
      { id: "admin",           category: "Admin",           view: false, create: false, edit: false, delete: false },
      { id: "backup",          category: "Backup",          view: false, create: false, edit: false, delete: false },
      { id: "system",          category: "System",          view: false, create: false, edit: false, delete: false },
    ],
  },
];
