// models/RBACPermission.js
// Stores the permission matrix for each role.
const mongoose = require("mongoose");

const permissionRowSchema = new mongoose.Schema(
  {
    id:       { type: String, required: true }, // e.g. 'document', 'email'
    category: { type: String, required: true }, // e.g. 'Document'
    view:     { type: Boolean, default: false },
    create:   { type: Boolean, default: false },
    edit:     { type: Boolean, default: false },
    delete:   { type: Boolean, default: false },
  },
  { _id: false }
);

const rbacPermissionSchema = new mongoose.Schema(
  {
    role:     { type: String, required: true, unique: true, lowercase: true },
    label:    { type: String, required: true },   // Display name e.g. "Admin"
    isSystem: { type: Boolean, default: false },  // System roles cannot be deleted
    permissions: { type: [permissionRowSchema], default: [] },
  },
  { timestamps: true }
);

module.exports = mongoose.model("RBACPermission", rbacPermissionSchema);
