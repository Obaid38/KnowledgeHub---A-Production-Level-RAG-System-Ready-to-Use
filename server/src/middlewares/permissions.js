// middlewares/permissions.js
// Fine-grained RBAC permission check middleware.
// Looks up the role's permission matrix in the DB and checks the required action.
//
// Usage:
//   const { can } = require("../middlewares/permissions");
//   router.delete("/docs", auth(), can("document", "delete"), ctrl.bulkDelete);

const RBACPermission = require("../models/RBACPermission");
const { forbidden }  = require("../utils/response");

// Map User.role enum values → RBACPermission role keys (lowercase)
const ROLE_MAP = {
  SuperAdmin: "admin",
  Admin:      "admin",
  Manager:    "manager",
  User:       "user",
  Viewer:     "viewer",
};

/**
 * can(permissionId, action)
 *
 * permissionId — one of the row IDs defined in RBACPermission
 *                e.g. "document" | "email" | "qa" | "knowledge-graph" |
 *                     "nlu" | "sap" | "admin" | "backup" | "system"
 * action       — "view" | "create" | "edit" | "delete"
 */
const can = (permissionId, action) => async (req, res, next) => {
  try {
    // SuperAdmins always have full access
    if (req.user?.role === "SuperAdmin") return next();

    const roleKey = ROLE_MAP[req.user?.role] ?? "user";
    const doc = await RBACPermission.findOne({ role: roleKey });

    // If no permissions are defined yet, default to deny
    if (!doc) return forbidden(res, "Permission not configured for this role");

    const row = doc.permissions.find((p) => p.id === permissionId);
    if (!row || !row[action]) {
      return forbidden(res, `You do not have '${action}' permission for '${permissionId}'`);
    }

    return next();
  } catch (err) {
    return next(err);
  }
};

module.exports = { can };
