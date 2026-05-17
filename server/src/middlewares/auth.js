// middlewares/auth.js
const { unauthorized, forbidden } = require("../utils/response");
const { verifyJwt } = require("../utils/jwt");
const User = require("../models/User");

function extractToken(req) {
  const h = req.headers.authorization || "";
  if (h.startsWith("Bearer ")) return h.slice(7).trim();
  return req.header("auth-token")?.trim() || null;
}

/**
 * auth(required = true)
 * Verifies the Bearer token and attaches req.user.
 * If required = false, unauthenticated requests pass through (req.user = null).
 */
const auth =
  (required = true) =>
  async (req, res, next) => {
    try {
      const token = extractToken(req);
      if (!token) return required ? unauthorized(res, "Missing Bearer token") : next();

      let decoded;
      try {
        decoded = verifyJwt(token);
      } catch {
        return unauthorized(res, "Invalid or expired token");
      }

      const user = await User.findById(decoded.sub).select("-password");
      if (!user) return forbidden(res, "Account not found or disabled");

      req.auth = decoded;
      req.user = user;
      return next();
    } catch (err) {
      return next(err);
    }
  };

/**
 * requireRoles(...roles)
 * Allows access only if req.user.role is in the allowed list.
 * Roles: "User" | "Admin" | "SuperAdmin"
 */
const requireRoles =
  (...allowed) =>
  (req, res, next) => {
    if (!req.user) return unauthorized(res, "Unauthorized");
    if (!allowed.includes(req.user.role)) return forbidden(res, "Insufficient role");
    return next();
  };

// Convenience guards
const superAdmin = requireRoles("SuperAdmin");
const admin      = requireRoles("Admin", "SuperAdmin");
const anyUser    = requireRoles("User", "Admin", "SuperAdmin");

module.exports = { auth, requireRoles, superAdmin, admin, anyUser };
