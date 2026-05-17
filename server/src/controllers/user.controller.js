// controllers/user.controller.js
const User           = require("../models/User");
const RBACPermission = require("../models/RBACPermission");
const {
  success,
  badRequest,
  notFound,
  requestConflict,
  systemfailure,
} = require("../utils/response");

// Roles that can be assigned to users (lowercase keys — must exist in RBACPermission)
const ASSIGNABLE_ROLES = ["user", "manager", "viewer", "admin"];

// ── Helpers ───────────────────────────────────────────────────────────────────

function userPublic(user, sn) {
  return {
    _id:       user._id,
    sn,
    firstName: user.firstName,
    lastName:  user.lastName,
    email:     user.email,
    role:      user.role,
    verified:  user.verified,
    createdAt: user.created_at ?? null,   // base.model uses snake_case timestamps
  };
}

// ── GET /users ────────────────────────────────────────────────────────────────

exports.listUsers = async (req, res) => {
  try {
    const { verified, page = 1, limit = 20 } = req.query;

    const filter = {};
    if (verified) filter.verified = verified; // 'Verified' | 'Unverified'

    const skip  = (Number(page) - 1) * Math.min(Number(limit), 100);
    const lim   = Math.min(Number(limit), 100);
    const total = await User.countDocuments(filter);
    const users = await User.find(filter)
      .sort({ createdAt: -1 })
      .skip(skip)
      .limit(lim);

    return success(res, {
      users: users.map((u, i) => userPublic(u, skip + i + 1)),
      pagination: {
        total,
        page:       Number(page),
        limit:      lim,
        totalPages: Math.ceil(total / lim),
      },
    });
  } catch (err) {
    return systemfailure(res, err);
  }
};

// ── POST /users/:id/approve ───────────────────────────────────────────────────

exports.approveUser = async (req, res) => {
  try {
    const { role } = req.body;

    if (!role) {
      return badRequest(res, "A role must be assigned when approving a user");
    }

    const roleKey = role.toLowerCase().trim();

    // Validate the role exists in the RBAC collection
    const roleDoc = await RBACPermission.findOne({ role: roleKey });
    if (!roleDoc) {
      return badRequest(res, `Role "${roleKey}" does not exist`);
    }

    const user = await User.findById(req.params.id);
    if (!user) return notFound(res, "User not found");

    if (user.verified === "Verified") {
      return requestConflict(res, "User is already verified");
    }

    // Capitalise role key to match User model enum (e.g. "admin" → "Admin")
    const roleEnum = roleKey.charAt(0).toUpperCase() + roleKey.slice(1);

    user.verified   = "Verified";
    user.verifiedAt = new Date();
    user.role       = roleEnum;
    await user.save();

    return success(res, { message: "User approved successfully.", role: roleEnum });
  } catch (err) {
    return systemfailure(res, err);
  }
};

// ── POST /users/:id/reject ────────────────────────────────────────────────────

exports.rejectUser = async (req, res) => {
  try {
    const user = await User.findById(req.params.id);
    if (!user) return notFound(res, "User not found");

    user.verified   = "Unverified";
    user.verifiedAt = null;
    await user.save();

    return success(res, { message: "User rejected." });
  } catch (err) {
    return systemfailure(res, err);
  }
};

// ── PATCH /users/:id/role ─────────────────────────────────────────────────────

exports.updateUserRole = async (req, res) => {
  try {
    const { role } = req.body;

    if (!role) {
      return badRequest(res, "A role is required");
    }

    const roleKey = role.toLowerCase().trim();

    const roleDoc = await RBACPermission.findOne({ role: roleKey });
    if (!roleDoc) {
      return badRequest(res, `Role "${roleKey}" does not exist`);
    }

    const user = await User.findById(req.params.id);
    if (!user) return notFound(res, "User not found");

    if (user._id.toString() === req.user._id.toString()) {
      return badRequest(res, "Cannot change your own role");
    }

    const roleEnum = roleKey.charAt(0).toUpperCase() + roleKey.slice(1);
    user.role = roleEnum;
    await user.save();

    return success(res, { message: "User role updated successfully.", role: roleEnum });
  } catch (err) {
    return systemfailure(res, err);
  }
};

// ── DELETE /users/:id ─────────────────────────────────────────────────────────

exports.deleteUser = async (req, res) => {
  try {
    const user = await User.findById(req.params.id);
    if (!user) return notFound(res, "User not found");

    if (user._id.toString() === req.user._id.toString()) {
      return badRequest(res, "Cannot delete your own account");
    }

    await user.deleteOne();
    return success(res, { message: "User deleted successfully." });
  } catch (err) {
    return systemfailure(res, err);
  }
};
