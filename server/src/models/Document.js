// models/Document.js
const mongoose = require("mongoose");

const documentSchema = new mongoose.Schema(
  {
    filename:   { type: String, required: true },
    mimetype:   { type: String, required: true },
    sizeBytes:  { type: Number, required: true },
    objectName: { type: String, required: true }, // MinIO key
    source:     { type: String, enum: ["Upload", "Email", "SAP", "API"], default: "Upload" },
    status:     { type: String, enum: ["Pending", "Processing", "Completed", "Failed"], default: "Pending" },
    category:   { type: String, enum: ["sop", "incident", "other", "compliance", "finance", "technical", "hr", "legal", "general", "cases"], default: "general" },
    uploadedBy: { type: mongoose.Schema.Types.ObjectId, ref: "User", required: true },
  },
  { timestamps: true }
);

// Virtual: human-readable size
documentSchema.virtual("size").get(function () {
  const bytes = this.sizeBytes;
  if (bytes < 1024)        return `${bytes} B`;
  if (bytes < 1024 ** 2)   return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 ** 3)   return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
  return `${(bytes / 1024 ** 3).toFixed(1)} GB`;
});

documentSchema.set("toJSON",   { virtuals: true });
documentSchema.set("toObject", { virtuals: true });

module.exports = mongoose.model("Document", documentSchema);
