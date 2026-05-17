// models/User.js
const { model } = require("mongoose");
const { buildSchema } = require("./base.model");
const passwordHashingPlugin = require("./plugins/passwordHashing.plugin");
const { hashPassword } = require("../utils/crypto");

const userSchema = buildSchema({
  firstName: { type: String, required: true, trim: true },
  lastName:  { type: String, required: true, trim: true },

  email: {
    type: String,
    required: true,
    lowercase: true,
    trim: true,
  },

  password: { type: String, required: true, minlength: 8, select: false },

  role: {
    type: String,
    enum: ["User", "Admin", "SuperAdmin", "Manager", "Viewer"],
    default: "User",
  },

  // 'Verified' once approved by admin, 'Unverified' while pending
  verified: {
    type: String,
    enum: ["Verified", "Unverified"],
    default: "Unverified",
  },
  verifiedAt: { type: Date, default: null },

  // MFA (TOTP via authenticator app)
  mfaEnabled:       { type: Boolean, default: false },
  mfaSecret:        { type: String,  default: null, select: false },
  mfaRecoveryCodes: {
    type: [
      {
        code: { type: String, required: true },
        used: { type: Boolean, default: false },
      },
    ],
    default: [],
    select: false,
  },

  // Password reset
  passwordResetToken:  { type: String, default: null, select: false },
  passwordResetExpiry: { type: Date,   default: null },
});

// Virtual
userSchema.virtual("fullName").get(function () {
  return `${this.firstName} ${this.lastName}`.trim();
});

// Unique email among non-deleted users
userSchema.index(
  { email: 1 },
  { unique: true, partialFilterExpression: { deleted_at: null } }
);

// Auto-hash password on save
userSchema.plugin(passwordHashingPlugin, { field: "password", hash: hashPassword });

module.exports = model("User", userSchema);
