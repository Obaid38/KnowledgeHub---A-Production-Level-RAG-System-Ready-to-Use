// controllers/rbac.controller.js
const RBACPermission = require("../models/RBACPermission");
const User           = require("../models/User");
const {
  success,
  badRequest,
  notFound,
  requestConflict,
  systemfailure,
} = require("../utils/response");

// ── System roles — these cannot be deleted ────────────────────────────────────
const SYSTEM_ROLES = ["admin", "manager", "user", "viewer"];

// ── Default permission rows aligned with RBAC Design Documentation ────────────
const DEFAULT_ROWS = [
  { id: "document",         category: "Document" },
  { id: "email",            category: "Email" },
  { id: "qa",               category: "Q&A" },
  { id: "knowledge-graph",  category: "Knowledge Graph" },
  { id: "nlu",              category: "NLU" },
  { id: "sap",              category: "SAP" },
  { id: "admin",            category: "Admin" },
  { id: "backup",           category: "Backup" },
  { id: "system",           category: "System" },
].map((r) => ({ ...r, view: false, create: false, edit: false, delete: false }));

// ── Default permissions per role (RBAC Design Doc) ────────────────────────────
const SYSTEM_ROLE_DEFAULTS = {
  admin: {
    label: "Admin",
    permissions: [
      { id: "document",        category: "Document",        view: true,  create: true,  edit: true,  delete: true },
      { id: "email",           category: "Email",           view: true,  create: true,  edit: true,  delete: true },
      { id: "qa",              category: "Q&A",             view: true,  create: true,  edit: true,  delete: true },
      { id: "knowledge-graph", category: "Knowledge Graph", view: true,  create: true,  edit: true,  delete: true },
      { id: "nlu",             category: "NLU",             view: true,  create: true,  edit: true,  delete: true },
      { id: "sap",             category: "SAP",             view: true,  create: true,  edit: true,  delete: true },
      { id: "admin",           category: "Admin",           view: true,  create: true,  edit: true,  delete: true },
      { id: "backup",          category: "Backup",          view: true,  create: true,  edit: true,  delete: true },
      { id: "system",          category: "System",          view: true,  create: true,  edit: true,  delete: true },
    ],
  },
  manager: {
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
  user: {
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
  viewer: {
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
};

// ── Helpers ───────────────────────────────────────────────────────────────────

function isValidRoleKey(role) {
  return /^[a-z][a-z0-9-]{1,39}$/.test(role);
}

/**
 * Count every individually-enabled action across all permission rows.
 * A row with view=true, edit=true counts as 2, not 1.
 */
function countPermissions(permissions) {
  return permissions.reduce(
    (acc, p) =>
      acc +
      (p.view   ? 1 : 0) +
      (p.create ? 1 : 0) +
      (p.edit   ? 1 : 0) +
      (p.delete ? 1 : 0),
    0
  );
}

/**
 * Upsert a role document.
 * For system roles  — always ensure label + isSystem:true are set.
 * For unknown roles — create with blank permissions if missing.
 * This handles upgrading old documents that pre-date the label/isSystem fields.
 */
async function getOrSeedRole(roleKey) {
  const defaults = SYSTEM_ROLE_DEFAULTS[roleKey];
  const isSystem = SYSTEM_ROLES.includes(roleKey);

  if (defaults) {
    // Use findOneAndUpdate with $setOnInsert to create if missing,
    // but always patch label + isSystem in case the doc was created by old code.
    const doc = await RBACPermission.findOneAndUpdate(
      { role: roleKey },
      {
        $set: {
          label:    defaults.label,
          isSystem: true,
        },
        $setOnInsert: {
          permissions: defaults.permissions,
        },
      },
      { upsert: true, new: true }
    );
    return doc;
  }

  // Custom / unknown role — create with blank rows if not found
  let doc = await RBACPermission.findOne({ role: roleKey });
  if (!doc) {
    doc = await RBACPermission.create({
      role:        roleKey,
      label:       roleKey.charAt(0).toUpperCase() + roleKey.slice(1),
      isSystem:    false,
      permissions: DEFAULT_ROWS,
    });
  }
  return doc;
}

// ── GET /rbac/roles ───────────────────────────────────────────────────────────

exports.listRoles = async (req, res) => {
  try {
    // Ensure all system roles exist and have correct label/isSystem
    await Promise.all(SYSTEM_ROLES.map(getOrSeedRole));

    const [roles, userCountAgg] = await Promise.all([
      RBACPermission.find().sort({ isSystem: -1, createdAt: 1 }),
      // One aggregation to get user counts keyed by lowercase role
      User.aggregate([
        { $group: { _id: { $toLower: "$role" }, count: { $sum: 1 } } },
      ]),
    ]);

    // Build a quick lookup: lowercase role key → user count
    const userCountMap = Object.fromEntries(
      userCountAgg.map(({ _id, count }) => [_id, count])
    );

    // Deduplicate by role key (safety net for legacy duplicate docs)
    const seen   = new Set();
    const unique = roles.filter((r) => {
      if (seen.has(r.role)) return false;
      seen.add(r.role);
      return true;
    });

    const shaped = unique.map((r) => ({
      role:            r.role,
      label:           r.label,
      isSystem:        r.isSystem,
      createdAt:       r.createdAt,
      permissionCount: countPermissions(r.permissions),
      userCount:       userCountMap[r.role] ?? 0,
    }));

    return success(res, { roles: shaped });
  } catch (err) {
    return systemfailure(res, err);
  }
};

// ── POST /rbac/roles ──────────────────────────────────────────────────────────

exports.createRole = async (req, res) => {
  try {
    const { role, label } = req.body;

    if (!role || !label) {
      return badRequest(res, "role (key) and label are required");
    }

    const roleKey = role.toLowerCase().trim();

    if (!isValidRoleKey(roleKey)) {
      return badRequest(res, "role key must be lowercase alphanumeric (hyphens allowed), 2-40 chars");
    }

    const existing = await RBACPermission.findOne({ role: roleKey });
    if (existing) {
      return requestConflict(res, `Role "${roleKey}" already exists`);
    }

    const doc = await RBACPermission.create({
      role:        roleKey,
      label:       label.trim(),
      isSystem:    false,
      permissions: DEFAULT_ROWS,
    });

    return success(res, { role: doc });
  } catch (err) {
    return systemfailure(res, err);
  }
};

// ── DELETE /rbac/roles/:role ──────────────────────────────────────────────────

exports.deleteRole = async (req, res) => {
  try {
    const roleKey = req.params.role.toLowerCase();

    if (SYSTEM_ROLES.includes(roleKey)) {
      return badRequest(res, "System roles cannot be deleted");
    }

    const doc = await RBACPermission.findOne({ role: roleKey });
    if (!doc) return notFound(res, "Role not found");

    await doc.deleteOne();

    return success(res, { message: `Role "${roleKey}" deleted successfully.` });
  } catch (err) {
    return systemfailure(res, err);
  }
};

// ── GET /rbac/roles/:role/permissions ─────────────────────────────────────────

exports.getPermissions = async (req, res) => {
  try {
    const roleKey = req.params.role.toLowerCase();

    if (!isValidRoleKey(roleKey)) {
      return badRequest(res, "Invalid role key");
    }

    const doc = await getOrSeedRole(roleKey);

    return success(res, {
      role:        doc.role,
      label:       doc.label,
      isSystem:    doc.isSystem,
      permissions: doc.permissions,
    });
  } catch (err) {
    return systemfailure(res, err);
  }
};

// ── PUT /rbac/roles/:role/permissions ─────────────────────────────────────────

exports.savePermissions = async (req, res) => {
  try {
    const roleKey = req.params.role.toLowerCase();
    const { permissions } = req.body;

    if (!isValidRoleKey(roleKey)) {
      return badRequest(res, "Invalid role key");
    }

    if (!Array.isArray(permissions)) {
      return badRequest(res, "permissions must be an array");
    }

    const doc = await RBACPermission.findOneAndUpdate(
      { role: roleKey },
      { permissions },
      { upsert: false, new: true }
    );

    if (!doc) return notFound(res, "Role not found — create the role first");

    return success(res, { message: "Permissions saved successfully." });
  } catch (err) {
    return systemfailure(res, err);
  }
};

// ── GET /rbac/roles/:role/stats ───────────────────────────────────────────────
// Returns per-role user count + enabled-permission count for the metric cards.

exports.getRoleStats = async (req, res) => {
  try {
    const roleKey = req.params.role.toLowerCase();

    if (!isValidRoleKey(roleKey)) {
      return badRequest(res, "Invalid role key");
    }

    // Capitalise to match User.role enum (e.g. "admin" → "Admin")
    const roleEnum = roleKey.charAt(0).toUpperCase() + roleKey.slice(1);

    const [doc, userCount] = await Promise.all([
      RBACPermission.findOne({ role: roleKey }),
      User.countDocuments({ role: roleEnum }),
    ]);

    const permissionCount = doc ? countPermissions(doc.permissions) : 0;

    return success(res, { userCount, permissionCount });
  } catch (err) {
    return systemfailure(res, err);
  }
};

// ── GET /rbac/metrics ─────────────────────────────────────────────────────────

exports.getMetrics = async (req, res) => {
  try {
    const [allPerms, activeUsers] = await Promise.all([
      RBACPermission.find(),
      User.countDocuments({ verified: "Verified" }),
    ]);

    const systemRoleCount = allPerms.filter((r) => r.isSystem).length;
    const customRoles     = allPerms.filter((r) => !r.isSystem).length;
    const totalRoles      = allPerms.length;

    const permissionsDefined = allPerms.reduce(
      (acc, r) => acc + countPermissions(r.permissions),
      0
    );

    return success(res, { systemRoles: totalRoles, permissionsDefined, activeUsers, customRoles, systemRoleCount });
  } catch (err) {
    return systemfailure(res, err);
  }
};
