// services/qdrant.service.js
// Direct Qdrant REST API client for managing embeddings from the Node backend.
//
// Architecture note: all document chunks live in a single "documents" collection.
// Category is stored as a payload field on each point — not as a collection name.
// Deleting a document → filter by doc_id in "documents".
// Changing a category → update the category payload field in-place (no cross-collection move).
const axios  = require("axios");
const config = require("../config");
const { logger } = require("../loaders/logging");

const QDRANT_COLLECTION = process.env.QDRANT_COLLECTION || "documents";

const qdrant = axios.create({
  baseURL: config.qdrant.url,
  timeout: 30_000,
});

/**
 * Delete all Qdrant points belonging to a document.
 * Called when a document is deleted from the system.
 *
 * @param {string} _category - Ignored (kept for call-site compat; all docs are in one collection)
 * @param {string} docId     - MongoDB document _id as a string
 * @param {string} filename  - Original filename for logging (optional)
 */
async function deleteDocumentChunks(_category, docId, filename = "") {
  const label = filename ? `${filename} (${docId})` : docId;
  try {
    await qdrant.post(`/collections/${QDRANT_COLLECTION}/points/delete`, {
      filter: {
        must: [{ key: "doc_id", match: { value: docId } }],
      },
    });
    logger.info(`[Qdrant] ✓ Chunks deleted  — ${label} — collection=${QDRANT_COLLECTION}`);
  } catch (err) {
    // Best-effort — log but never block the main flow
    logger.warn(`[Qdrant] ✗ Delete FAILED  — ${label} — collection=${QDRANT_COLLECTION} — ${err.message}`);
  }
}

/**
 * Update the category payload field for all Qdrant points belonging to a document.
 * Called when a document's category is changed via the UI.
 *
 * All chunks stay in the same "documents" collection — only their category
 * payload value is updated (no cross-collection copy/delete required).
 *
 * @param {string} _fromCategory - Ignored (category was stored as payload, not collection)
 * @param {string} toCategory    - New category value (stored lowercase)
 * @param {string} docId         - MongoDB document _id as a string
 */
async function moveDocumentChunks(_fromCategory, toCategory, docId) {
  const normalizedCategory = toCategory.toLowerCase();

  try {
    // Qdrant payload update by filter — updates all matching points atomically
    await qdrant.post(`/collections/${QDRANT_COLLECTION}/points/payload`, {
      payload: { category: normalizedCategory },
      filter: {
        must: [{ key: "doc_id", match: { value: docId } }],
      },
    });
    logger.info(
      `Qdrant: updated category to '${normalizedCategory}' for doc=${docId} collection=${QDRANT_COLLECTION}`
    );
  } catch (err) {
    logger.warn(
      `Qdrant: category update failed doc=${docId} → ${normalizedCategory}: ${err.message}`
    );
  }
}

module.exports = { deleteDocumentChunks, moveDocumentChunks };
