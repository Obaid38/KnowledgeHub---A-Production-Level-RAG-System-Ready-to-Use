// services/ai.service.js
// Thin HTTP client for the Python AI/RAG backend.
const axios  = require("axios");
const config = require("../config");
const { logger } = require("../loaders/logging");

// ── RAG query client (existing) ───────────────────────────────────────────────
const queryClient = axios.create({
  baseURL: config.ai.baseUrl,
  timeout: config.ai.timeout,
});
// ── Ingest client (Python AI ingest service) ──────────────────────────────────
const ingestClient = axios.create({
  baseURL: config.ai.ingestUrl,
  timeout: config.ai.ingestTimeout,
});
console.log(`AI service ingest URL: ${config.ai.ingestUrl}`);

/**
 * POST /api/ingest-documents
 * Tells the AI service to pull a document from MinIO and embed it.
 *
 * @param {Object} params
 * @param {string} params.userId     - MongoDB user _id (string)
 * @param {string} params.category   - Document category (SOP, Incident, …)
 * @param {string} params.filename   - Original filename
 * @param {string} params.objectKey  - MinIO object key (path inside bucket)
 * @param {string} params.docId      - MongoDB document _id (string)
 */
console.log("bucketname: ", config.minio.bucket);
async function ingestDocument({ userId, category, filename, objectKey, docId }) {
  try {
    await ingestClient.post("/api/ingest-documents", [
      {
        user_id:    userId,
        category,
        filename,
        bucketname: config.minio.bucket,
        objectKey,
        doc_id:     docId,
      },
    ]);
    logger.info(`AI ingest queued: doc=${docId} file=${filename}`);
  } catch (err) {
    logger.warn(`AI ingest error for doc ${docId}: ${err.message}`);
    throw err;
  }
}

function fileTypeFromName(filename = "") {
  const ext = filename.split(".").pop();
  return ext && ext !== filename ? ext.toUpperCase() : "DOC";
}

function mapCitationToSource(citation) {
  const filename = citation?.source_filename || "Unknown source";
  return {
    id:       `source-${citation?.rank ?? filename}`,
    filename,
    type:     fileTypeFromName(filename),
    page:     citation?.page_number ?? undefined,
  };
}

/**
 * POST /api/qa/ask  — RAG query with session persistence.
 * Returns { answer, sources, confidence }
 *
 * @param {string}   params.question           - The user's question
 * @param {string}   [params.sessionId]        - MongoDB conversation _id string (for Redis session)
 * @param {string[]} [params.collection_filter] - Qdrant collections to search (null = all)
 */
async function query({ question, sessionId = null, conversationHistory = [], mode = "rag", collection_filter = null }) {
  console.log("AI query received:", { question, mode, sessionId, collection_filter });
  try {
    const { data } = await queryClient.post("/api/qa/ask", {
      query:             question,
      session_id:        sessionId,
      collection_filter: collection_filter && collection_filter.length > 0 ? collection_filter : null,
    });
    return {
      answer:     data.answer,
      sources:    Array.isArray(data.citations) ? data.citations.map(mapCitationToSource) : [],
      confidence: data.top_score ?? 0,
    };
  } catch (err) {
    logger.warn(`AI service /api/qa/ask error: ${err.message}`);
    throw err;
  }
}

module.exports = { ingestDocument, query };
