// controllers/auth.controller.js
const speakeasy      = require("speakeasy");
const qrcode         = require("qrcode");
const crypto         = require("crypto");

const User           = require("../models/User");
const RBACPermission = require("../models/RBACPermission");
const { comparePassword } = require("../utils/crypto");
const { signJwt, verifyJwt } = require("../utils/jwt");
const { sendPasswordReset } = require("../services/email/email.service");
const {
  generateResetToken,
  generateResetTokenExpiry,
  isResetTokenExpired,
  isValidResetTokenFormat,
  createResetUrl,
  hashResetToken,
  verifyResetToken,
} = require("../utils/passwordReset");
const config = require("../config");
const {
  success,
  created,
  badRequest,
  unauthorized,
  requestConflict,
  systemfailure,
} = require("../utils/response");

// ── Helpers ───────────────────────────────────────────────────────────────────

function userPublic(user) {
  return {
    _id:        user._id,
    email:      user.email,
    firstName:  user.firstName,
    lastName:   user.lastName,
    role:       user.role,
    mfaEnabled: user.mfaEnabled,
  };
}

/** Map the User.role enum to the RBAC permission-row key. */
function toRbacKey(role) {
  switch ((role || "").toLowerCase()) {
    case "superadmin": return "admin";
    case "admin":      return "admin";
    case "manager":    return "manager";
    case "user":       return "user";
    case "viewer":     return "viewer";
    default:           return null;
  }
}

/**
 * Build the full auth payload that includes the permission matrix.
 * Permissions are fetched directly — no auth middleware check — so any
 * verified user can receive their own permissions on login / /me.
 */
async function buildUserResponse(user) {
  const rbacKey     = toRbacKey(user.role);
  let   permissions = [];

  if (rbacKey) {
    try {
      const doc = await RBACPermission.findOne({ role: rbacKey });
      permissions = doc ? doc.permissions : [];
    } catch {
      // Non-fatal: the user still logs in; permissions default to empty
    }
  }

  return { ...userPublic(user), permissions };
}

function signMfaToken(userId) {
  return signJwt(
    { sub: userId.toString(), type: "mfa" },
    { secret: config.jwt.mfaSecret, expiresIn: config.jwt.mfaExpiresIn }
  );
}

function signAccessToken(user) {
  return signJwt({
    sub:   user._id.toString(),
    role:  user.role,
    email: user.email,
  });
}

// ── POST /auth/register ───────────────────────────────────────────────────────

exports.register = async (req, res) => {
  try {
    const { firstName, lastName, email, password } = req.body || {};

    const existing = await User.findOne({ email });
    if (existing) return requestConflict(res, "Email already registered");

    const user = await User.create({
      firstName,
      lastName,
      email,
      password,
      role:     "User",
      verified: "Unverified",
    });

    return created(res, {
      message: "Account created. Awaiting admin approval.",
      user:    userPublic(user),
    });
  } catch (err) {
    return systemfailure(res, err);
  }
};

// ── POST /auth/login ──────────────────────────────────────────────────────────

exports.login = async (req, res) => {
  try {
    const { email, password } = req.body || {};

    const user = await User.findOne({ email }).select("+password");
    if (!user) return unauthorized(res, "Invalid email or password", "INVALID_CREDENTIALS");

    const ok = await comparePassword(password, user.password);
    if (!ok) return unauthorized(res, "Invalid email or password", "INVALID_CREDENTIALS");

    if (user.verified !== "Verified") {
      return unauthorized(res, "Account awaiting admin approval", "ACCOUNT_PENDING");
    }

    // MFA enabled → return short-lived mfaToken
    if (user.mfaEnabled) {
      const mfaToken = signMfaToken(user._id);
      return success(res, {
        mfaRequired: true,
        mfaToken,
        email: user.email,
      });
    }

    // No MFA → return full JWT
    const token    = signAccessToken(user);
    const userResp = await buildUserResponse(user);
    return success(res, {
      mfaRequired: false,
      token,
      user: userResp,
    });
  } catch (err) {
    return systemfailure(res, err);
  }
};

// ── POST /auth/verify-mfa ─────────────────────────────────────────────────────

exports.verifyMfa = async (req, res) => {
  try {
    const { mfaToken, code } = req.body || {};

    let decoded;
    try {
      decoded = verifyJwt(mfaToken, { secret: config.jwt.mfaSecret });
    } catch {
      return unauthorized(res, "mfaToken has expired. Please login again", "MFA_TOKEN_EXPIRED");
    }

    if (decoded.type !== "mfa") {
      return unauthorized(res, "Invalid MFA token", "MFA_TOKEN_EXPIRED");
    }

    const user = await User.findById(decoded.sub).select("+mfaSecret");
    if (!user) return unauthorized(res, "User not found", "UNAUTHORIZED");

    const valid = speakeasy.totp.verify({
      secret:   user.mfaSecret,
      encoding: "base32",
      token:    code,
      window:   1, // allow ±30 s clock drift
    });

    if (!valid) return unauthorized(res, "Incorrect or expired code", "INVALID_MFA_CODE");

    const token    = signAccessToken(user);
    const userResp = await buildUserResponse(user);
    return success(res, { token, user: userResp });
  } catch (err) {
    return systemfailure(res, err);
  }
};

// ── POST /auth/verify-mfa-recovery ───────────────────────────────────────────

exports.verifyMfaRecovery = async (req, res) => {
  try {
    const { mfaToken, recoveryCode } = req.body || {};

    let decoded;
    try {
      decoded = verifyJwt(mfaToken, { secret: config.jwt.mfaSecret });
    } catch {
      return unauthorized(res, "Session expired. Please login again", "MFA_TOKEN_EXPIRED");
    }

    const user = await User.findById(decoded.sub).select("+mfaRecoveryCodes");
    if (!user) return unauthorized(res, "User not found", "UNAUTHORIZED");

    const entry = user.mfaRecoveryCodes.find(
      (r) => !r.used && r.code === recoveryCode
    );
    if (!entry) {
      return unauthorized(res, "Recovery code is invalid or already used", "INVALID_RECOVERY_CODE");
    }

    entry.used = true;
    await user.save();

    const token    = signAccessToken(user);
    const userResp = await buildUserResponse(user);
    return success(res, { token, user: userResp });
  } catch (err) {
    return systemfailure(res, err);
  }
};

// ── POST /auth/forgot-password ────────────────────────────────────────────────

exports.forgotPassword = async (req, res) => {
  try {
    const { email } = req.body || {};

    const user = await User.findOne({ email });
    // Always return the same message (prevent email enumeration)
    const msg = "If that email exists, a reset link has been sent.";

    if (!user || user.verified !== "Verified") return success(res, { message: msg });

    const resetToken  = generateResetToken();
    const hashedToken = hashResetToken(resetToken);

    user.passwordResetToken  = hashedToken;
    user.passwordResetExpiry = generateResetTokenExpiry();
    await user.save();

    const resetUrl = createResetUrl(resetToken);
    await sendPasswordReset({
      to:            user.email,
      name:          `${user.firstName} ${user.lastName}`.trim(),
      resetUrl,
      expiryMinutes: config.passwordReset.expiryMinutes,
    });

    return success(res, { message: msg });
  } catch (err) {
    return systemfailure(res, err);
  }
};

// ── POST /auth/reset-password ─────────────────────────────────────────────────

exports.resetPassword = async (req, res) => {
  try {
    const { token, password } = req.body || {};

    if (!isValidResetTokenFormat(token)) {
      return badRequest(res, "Reset token is invalid", "INVALID_TOKEN");
    }

    const user = await User.findOne({
      passwordResetToken: hashResetToken(token),
    }).select("+passwordResetToken");

    if (!user) return badRequest(res, "Reset token is invalid", "INVALID_TOKEN");

    if (isResetTokenExpired(user.passwordResetExpiry)) {
      user.passwordResetToken  = null;
      user.passwordResetExpiry = null;
      await user.save();
      return badRequest(res, "Reset token has expired", "TOKEN_EXPIRED");
    }

    if (!verifyResetToken(token, user.passwordResetToken)) {
      return badRequest(res, "Reset token is invalid", "INVALID_TOKEN");
    }

    user.password            = password;
    user.passwordResetToken  = null;
    user.passwordResetExpiry = null;
    await user.save();

    return success(res, { message: "Password has been reset successfully." });
  } catch (err) {
    return systemfailure(res, err);
  }
};

// ── POST /auth/mfa/setup  (generate secret + QR) ─────────────────────────────

exports.mfaSetup = async (req, res) => {
  try {
    const user = await User.findById(req.user._id);
    if (!user) return unauthorized(res, "User not found");

    const secret = speakeasy.generateSecret({
      name:   `${config.emailBrand.appName} (${user.email})`,
      length: 20,
    });

    user.mfaSecret = secret.base32;
    await user.save();

    const otpauthUrl = secret.otpauth_url;
    const qrDataUrl  = await qrcode.toDataURL(otpauthUrl);

    return success(res, { secret: secret.base32, qrCode: qrDataUrl });
  } catch (err) {
    return systemfailure(res, err);
  }
};

// ── POST /auth/mfa/enable  (confirm TOTP code and activate MFA) ───────────────

exports.mfaEnable = async (req, res) => {
  try {
    const { code } = req.body || {};
    const user = await User.findById(req.user._id).select("+mfaSecret");
    if (!user) return unauthorized(res, "User not found");

    const valid = speakeasy.totp.verify({
      secret:   user.mfaSecret,
      encoding: "base32",
      token:    code,
      window:   1,
    });

    if (!valid) return badRequest(res, "Incorrect TOTP code", "INVALID_MFA_CODE");

    // Generate 8 one-time recovery codes
    const recoveryCodes = Array.from({ length: 8 }, () => ({
      code: crypto.randomBytes(5).toString("hex").toUpperCase(),
      used: false,
    }));

    user.mfaEnabled       = true;
    user.mfaRecoveryCodes = recoveryCodes;
    await user.save();

    return success(res, {
      message:       "MFA enabled successfully.",
      recoveryCodes: recoveryCodes.map((r) => r.code),
    });
  } catch (err) {
    return systemfailure(res, err);
  }
};

// ── POST /auth/mfa/disable ────────────────────────────────────────────────────

exports.mfaDisable = async (req, res) => {
  try {
    const { code } = req.body || {};
    const user = await User.findById(req.user._id).select("+mfaSecret");
    if (!user) return unauthorized(res, "User not found");

    const valid = speakeasy.totp.verify({
      secret:   user.mfaSecret,
      encoding: "base32",
      token:    code,
      window:   1,
    });

    if (!valid) return badRequest(res, "Incorrect TOTP code", "INVALID_MFA_CODE");

    user.mfaEnabled       = false;
    user.mfaSecret        = null;
    user.mfaRecoveryCodes = [];
    await user.save();

    return success(res, { message: "MFA disabled." });
  } catch (err) {
    return systemfailure(res, err);
  }
};

// ── POST /auth/change-password ────────────────────────────────────────────────

exports.changePassword = async (req, res) => {
  try {
    const { currentPassword, newPassword } = req.body || {};

    const user = await User.findById(req.user._id).select("+password");
    if (!user) return unauthorized(res, "User not found");

    const ok = await comparePassword(currentPassword, user.password);
    if (!ok) return badRequest(res, "Current password is incorrect", "INVALID_CURRENT_PASSWORD");

    if (currentPassword === newPassword) {
      return badRequest(res, "New password must differ from current password", "SAME_PASSWORD");
    }

    user.password = newPassword;
    await user.save();

    return success(res, { message: "Password changed successfully." });
  } catch (err) {
    return systemfailure(res, err);
  }
};

// ── PATCH /auth/me  (update firstName / lastName) ────────────────────────────

exports.updateProfile = async (req, res) => {
  try {
    const { firstName, lastName } = req.body || {};
    const user = await User.findById(req.user._id);
    if (!user) return unauthorized(res, "User not found");

    if (firstName !== undefined) user.firstName = firstName.trim();
    if (lastName  !== undefined) user.lastName  = lastName.trim();
    await user.save();

    return success(res, { user: userPublic(user) });
  } catch (err) {
    return systemfailure(res, err);
  }
};

// ── GET /auth/me  (current user profile from token) ──────────────────────────

exports.me = async (req, res) => {
  try {
    const user     = await User.findById(req.user._id);
    if (!user) return unauthorized(res, "User not found");
    const userResp = await buildUserResponse(user);
    return success(res, { user: userResp });
  } catch (err) {
    return systemfailure(res, err);
  }
};
