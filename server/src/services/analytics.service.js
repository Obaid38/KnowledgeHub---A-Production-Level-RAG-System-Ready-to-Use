// services/analytics.service.js
// Reusable aggregation helpers for document and message (AI query) counts.
// Import and call these anywhere — dashboard, reporting, etc.

const Document     = require("../models/Document");
const Conversation = require("../models/Conversation");

// ─── Message (AI query) helpers ───────────────────────────────────────────────

/**
 * Count total AI messages across all conversations.
 * Optionally filter by a date range on messages.createdAt.
 *
 * @param {{ from?: Date, to?: Date }} [range]
 * @returns {Promise<number>}
 */
async function countMessages({ from, to } = {}) {
  const pipeline = [{ $unwind: "$messages" }];

  if (from || to) {
    const filter = {};
    if (from) filter.$gte = from;
    if (to)   filter.$lt  = to;
    pipeline.push({ $match: { "messages.createdAt": filter } });
  }

  pipeline.push({ $count: "total" });

  const result = await Conversation.aggregate(pipeline);
  return result[0]?.total ?? 0;
}

/**
 * Count messages grouped by time-period bucket for time-series charts.
 * Messages are grouped by their own createdAt timestamp (set by Mongoose
 * subdocument timestamps), matching the same total that countMessages() returns.
 *
 * @param {Date}   from        - start date (inclusive)
 * @param {string} groupFormat - MongoDB $dateToString format:
 *                               "%Y-%m-%d" for daily
 *                               "%G-%V"    for ISO weekly
 *                               "%Y-%m"    for monthly
 * @returns {Promise<Array<{ _id: string, count: number }>>}
 */
async function countMessagesByPeriod(from, groupFormat) {
  return Conversation.aggregate([
    { $unwind: "$messages" },
    { $match: { "messages.createdAt": { $gte: from } } },
    {
      $group: {
        _id:   { $dateToString: { format: groupFormat, date: "$messages.createdAt" } },
        count: { $sum: 1 },
      },
    },
  ]);
}

// ─── Document helpers ─────────────────────────────────────────────────────────

/**
 * Count documents grouped by time-period bucket.
 *
 * @param {Date}   from        - start date (inclusive)
 * @param {string} groupFormat - same format strings as countMessagesByPeriod
 * @returns {Promise<Array<{ _id: string, count: number }>>}
 */
async function countDocumentsByPeriod(from, groupFormat) {
  return Document.aggregate([
    { $match: { createdAt: { $gte: from } } },
    {
      $group: {
        _id:   { $dateToString: { format: groupFormat, date: "$createdAt" } },
        count: { $sum: 1 },
      },
    },
  ]);
}

module.exports = { countMessages, countMessagesByPeriod, countDocumentsByPeriod };
