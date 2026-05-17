// controllers/document.controller.js
const Document    = require("../models/Document");
const minioSvc    = require("../services/minio.service");
const aiSvc       = require("../services/ai.service");
const qdrantSvc   = require("../services/qdrant.service");
const socketSvc   = require("../services/socket.service");
const config      = require("../config");
const { logger }  = require("../loaders/logging");
const {
  success,
  created,
  badRequest,
  notFound,
  forbidden,
  systemfailure,
} = require("../utils/response");

const ALLOWED_MIMETYPES = [
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  "application/vnd.openxmlformats-officedocument.presentationml.presentation",
  "text/plain",
  "image/png",
  "image/jpeg",
];
const MAX_SIZE_BYTES = 50 * 1024 * 1024; // 50 MB

function docOut(doc) {
  const obj = doc.toObject();
  delete obj.objectName; // internal key — never expose
  return obj;
}

// ── POST /documents/upload ────────────────────────────────────────────────────

exports.upload = async (req, res) => {
  try {
    const files    = req.files;
    // Category is optional — default to "general" when not provided or empty.
    const rawCategory = (req.body.category || "").trim().toLowerCase();
    const validCategories = ["sop", "incident", "other", "compliance", "finance", "technical", "hr", "legal", "general", "cases"];
    const category = validCategories.includes(rawCategory) ? rawCategory : "general";

    if (!files || files.length === 0) {
      return badRequest(res, "At least one file is required", "NO_FILE");
    }

    const saved = [];

    for (const file of files) {
      if (!ALLOWED_MIMETYPES.includes(file.mimetype)) {
        return badRequest(res, `Unsupported file type: ${file.mimetype}`);
      }
      if (file.size > MAX_SIZE_BYTES) {
        return badRequest(res, "Max file size is 50 MB", "FILE_TOO_LARGE");
      }

      let objectName;
      try {
        objectName = await minioSvc.uploadFile({
          buffer:       file.buffer,
          originalName: file.originalname,
          mimetype:     file.mimetype,
        });
      } catch (e) {
        return res.status(500).json({
          success: false,
          error: { code: "STORAGE_ERROR", message: "Failed to store file" },
        });
      }

      const doc = await Document.create({
        filename:   file.originalname,
        mimetype:   file.mimetype,
        sizeBytes:  file.size,
        objectName,
        source:     "Upload",
        status:     "Pending",
        category,
        uploadedBy: req.user._id,
      });

      saved.push(docOut(doc));

      // Broadcast activity to all dashboard clients
      socketSvc.emitActivity({
        id:        `upload-${doc._id}`,
        type:      "upload",
        text:      `${file.originalname} uploaded`,
        timestamp: doc.createdAt,
      });
    }

    return created(res, { documents: saved });
  } catch (err) {
    return systemfailure(res, err);
  }
};

// ── POST /documents/process ───────────────────────────────────────────────────

exports.process = async (req, res) => {
  try {
    const { documentIds, category } = req.body;

    if (!documentIds || !documentIds.length) {
      return badRequest(res, "No document IDs provided", "MISSING_DOCUMENT_IDS");
    }

    const docs = await Document.find({ _id: { $in: documentIds } });
    if (docs.length !== documentIds.length) {
      return notFound(res, "One or more documents not found", "DOCUMENT_NOT_FOUND");
    }

    // Mark all as Processing immediately so the UI reflects the state
    await Document.updateMany(
      { _id: { $in: documentIds } },
      { status: "Processing", ...(category ? { category } : {}) }
    );

    // Respond immediately — the actual AI ingestion runs in the background
    // so the HTTP request doesn't block waiting for the AI service.
    res.status(200).json({
      success: true,
      data: { documentIds, message: "Processing started" },
    });

    const results = await Promise.allSettled(
      docs.map((doc) =>
        aiSvc.ingestDocument({
          userId:    doc.uploadedBy.toString(),
          category:  category || doc.category || "general",
          filename:  doc.filename,
          objectKey: doc.objectName,
          docId:     doc._id.toString(),
        })
      )
    );
    await Promise.all(
      results.map((result, i) => {
        const status = result.status === "fulfilled" ? "Completed" : "Failed";
        const doc    = docs[i];
        // Push real-time status to the user's browser
        socketSvc.emitDocumentStatus(doc.uploadedBy.toString(), doc._id.toString(), status);
        // Broadcast processing result to all dashboard clients
        socketSvc.emitActivity({
          id:        `proc-${doc._id}`,
          type:      "processing",
          text:      `Document processing ${status.toLowerCase()}: ${doc.filename}`,
          timestamp: new Date().toISOString(),
        });
        return Document.findByIdAndUpdate(doc._id, { status });
      })
    );
  } catch (err) {
    return systemfailure(res, err);
  }
};

// ── GET /documents ────────────────────────────────────────────────────────────

exports.list = async (req, res) => {
  try {
    const { status, category, source, page = 1, limit = 20 } = req.query;

    const filter = {};
    // Non-admins see only their own documents
    if (!["Admin", "SuperAdmin"].includes(req.user.role)) {
      filter.uploadedBy = req.user._id;
    }
    if (status)   filter.status   = status;
    if (category) filter.category = category;
    if (source)   filter.source   = source;

    const lim   = Math.min(Number(limit), 100);
    const skip  = (Number(page) - 1) * lim;
    const total = await Document.countDocuments(filter);
    const docs  = await Document.find(filter)
      .sort({ createdAt: -1 })
      .skip(skip)
      .limit(lim)
      .populate("uploadedBy", "firstName lastName email");

    return success(res, {
      documents: docs.map(docOut),
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

// ── GET /documents/:id/download ───────────────────────────────────────────────

exports.download = async (req, res) => {
  try {
    const doc = await Document.findById(req.params.id);
    if (!doc) return notFound(res, "Document not found");

    // Access check for non-admins
    if (
      !["Admin", "SuperAdmin"].includes(req.user.role) &&
      doc.uploadedBy.toString() !== req.user._id.toString()
    ) {
      return forbidden(res, "Access denied to this document");
    }

    let url;
    try {
      url = await minioSvc.presignedUrl(doc.objectName, 900); // 15 min
    } catch {
      return res.status(500).json({
        success: false,
        error: { code: "STORAGE_ERROR", message: "Failed to generate download URL" },
      });
    }

    const expiresAt = new Date(Date.now() + 900_000).toISOString();
    return success(res, { url, expiresAt });
  } catch (err) {
    return systemfailure(res, err);
  }
};

// ── GET /documents/:id/preview ────────────────────────────────────────────────

exports.preview = async (req, res) => {
  try {
    const doc = await Document.findById(req.params.id);
    if (!doc) return notFound(res, "Document not found");

    if (
      !["Admin", "SuperAdmin"].includes(req.user.role) &&
      doc.uploadedBy.toString() !== req.user._id.toString()
    ) {
      return forbidden(res, "Access denied to this document");
    }

    let url;
    try {
      // 1-hour expiry for preview — enough time to render the document
      url = await minioSvc.presignedUrl(doc.objectName, 3600);
    } catch {
      return res.status(500).json({
        success: false,
        error: { code: "STORAGE_ERROR", message: "Failed to generate preview URL" },
      });
    }

    const expiresAt = new Date(Date.now() + 3600_000).toISOString();
    return success(res, {
      url,
      expiresAt,
      filename: doc.filename,
      mimetype: doc.mimetype,
    });
  } catch (err) {
    return systemfailure(res, err);
  }
};

// ── PATCH /documents/category ─────────────────────────────────────────────────

exports.bulkUpdateCategory = async (req, res) => {
  try {
    const { ids, category } = req.body;

    if (!Array.isArray(ids) || ids.length === 0) {
      return badRequest(res, "ids must be a non-empty array");
    }
    if (ids.length > 200) return badRequest(res, "Max 200 IDs per request");

    const validCategories = ["sop", "incident", "other", "compliance", "finance", "technical", "hr", "legal", "general", "cases"];
    const normCategory = (category || "").trim().toLowerCase();
    if (!validCategories.includes(normCategory)) {
      return badRequest(res, `Invalid category value '${category}'. Allowed: ${validCategories.join(", ")}`);
    }

    // Fetch current docs to know each one's old category before updating
    const docs = await Document.find({ _id: { $in: ids } }, { _id: 1, category: 1 });

    const result = await Document.updateMany(
      { _id: { $in: ids } },
      { category: normCategory }
    );

    // Best-effort: update category payload in Qdrant for each doc that changed
    for (const doc of docs) {
      if (doc.category !== normCategory) {
        qdrantSvc.moveDocumentChunks(doc.category, normCategory, doc._id.toString());
      }
    }

    return success(res, {
      updated: result.modifiedCount,
      message: `${result.modifiedCount} documents updated successfully.`,
    });
  } catch (err) {
    return systemfailure(res, err);
  }
};

// ── DELETE /documents ─────────────────────────────────────────────────────────

exports.bulkDelete = async (req, res) => {
  try {
    const { ids } = req.body;

    if (!Array.isArray(ids) || ids.length === 0) {
      return badRequest(res, "ids must be a non-empty array");
    }
    if (ids.length > 200) return badRequest(res, "Max 200 IDs per request");

    const docs = await Document.find({ _id: { $in: ids } });
    if (!docs.length) {
      return success(res, { deleted: 0, message: "0 documents deleted successfully." });
    }

    // Remove DB records first
    await Document.deleteMany({ _id: { $in: ids } });

    // Then remove from MinIO (best-effort)
    try {
      await minioSvc.deleteFiles(docs.map((d) => d.objectName));
    } catch (e) {
      return res.status(500).json({
        success: false,
        error: { code: "STORAGE_ERROR", message: "Failed to delete files from storage" },
      });
    }

    // Best-effort: remove embeddings from Qdrant for each deleted document
    logger.info(
      `[BulkDelete] Removing Qdrant chunks for ${docs.length} doc(s): ${docs.map((d) => d.filename || d._id).join(", ")}`
    );
    for (const doc of docs) {
      await qdrantSvc.deleteDocumentChunks(doc.category, doc._id.toString(), doc.filename);
    }
    logger.info(`[BulkDelete] Qdrant cleanup complete for ${docs.length} doc(s)`);

    return success(res, {
      deleted: docs.length,
      message: `${docs.length} documents deleted successfully.`,
    });
  } catch (err) {
    return systemfailure(res, err);
  }
};
