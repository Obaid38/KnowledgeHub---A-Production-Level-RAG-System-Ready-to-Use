// controllers/dashboard.controller.js
const Document      = require("../models/Document");
const Conversation  = require("../models/Conversation");
const analyticsSvc  = require("../services/analytics.service");
const { success, systemfailure } = require("../utils/response");

// ─── Helpers ──────────────────────────────────────────────────────────────────

/**
 * Build a lookup map from an aggregate result: { _id, count }[]
 * keyed by _id string.
 */
function buildCountMap(agg) {
  return Object.fromEntries(agg.map((a) => [String(a._id), a.count]));
}

// ── GET /dashboard/metrics ────────────────────────────────────────────────────

exports.getMetrics = async (req, res) => {
  try {
    const now       = new Date();
    const startOfDay = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const yesterday  = new Date(startOfDay.getTime() - 86400000);

    const [
      totalDocuments,
      docsToday,
      docsYesterday,
      processingCount,
      totalMessages,
      messagesToday,
      messagesYesterday,
    ] = await Promise.all([
      Document.countDocuments(),
      Document.countDocuments({ createdAt: { $gte: startOfDay } }),
      Document.countDocuments({ createdAt: { $gte: yesterday, $lt: startOfDay } }),
      Document.countDocuments({ status: "Processing" }),
      analyticsSvc.countMessages(),
      analyticsSvc.countMessages({ from: startOfDay }),
      analyticsSvc.countMessages({ from: yesterday, to: startOfDay }),
    ]);

    // Confidence: average of last 100 completed QA answers
    const latestConvos = await Conversation.find()
      .sort({ updatedAt: -1 })
      .limit(20)
      .select("messages");

    let totalConf = 0;
    let confCount  = 0;
    for (const c of latestConvos) {
      for (const m of c.messages) {
        for (const a of m.answers) {
          if (a.confidence) { totalConf += a.confidence; confCount++; }
        }
      }
    }
    const avgConfidence = confCount > 0 ? Math.round(totalConf / confCount) : 0;

    return success(res, {
      totalDocuments: {
        value:       totalDocuments,
        changeCount: docsToday - docsYesterday,
      },
      aiQueries: {
        value:     totalMessages,
        changePct: messagesYesterday > 0
          ? Math.round(((messagesToday - messagesYesterday) / messagesYesterday) * 100)
          : 0,
      },
      processingCount: { value: processingCount },
      confidenceScore: {
        value:     avgConfidence,
        changePct: 0,
      },
    });
  } catch (err) {
    return systemfailure(res, err);
  }
};

// ── GET /dashboard/query-volume ───────────────────────────────────────────────

exports.getQueryVolume = async (req, res) => {
  try {
    const { period = "daily" } = req.query;

    const now = new Date();
    now.setHours(23, 59, 59, 999);

    let categories     = [];
    let dateKeys       = [];
    let matchStart;
    let docGroupFormat;
    let queryGroupFormat;

    if (period === "daily") {
      // Last 7 days
      for (let i = 6; i >= 0; i--) {
        const d = new Date(now);
        d.setDate(d.getDate() - i);
        categories.push(d.toLocaleDateString("en-US", { weekday: "short" }));
        dateKeys.push(d.toISOString().slice(0, 10));
      }
      matchStart       = new Date(now);
      matchStart.setDate(matchStart.getDate() - 6);
      matchStart.setHours(0, 0, 0, 0);
      docGroupFormat   = "%Y-%m-%d";
      queryGroupFormat = "%Y-%m-%d";

    } else if (period === "weekly") {
      // Last 7 weeks — label as "Wk N" relative to oldest
      for (let i = 6; i >= 0; i--) {
        categories.push(`Wk ${7 - i}`);
        const weekEnd = new Date(now);
        weekEnd.setDate(weekEnd.getDate() - i * 7);
        const weekNum = getISOWeek(weekEnd);
        const year    = weekEnd.getFullYear();
        dateKeys.push(`${year}-${String(weekNum).padStart(2, "0")}`);
      }
      matchStart       = new Date(now);
      matchStart.setDate(matchStart.getDate() - 6 * 7);
      matchStart.setHours(0, 0, 0, 0);
      docGroupFormat   = "%G-%V";
      queryGroupFormat = "%G-%V";

    } else {
      // monthly — last 12 months
      for (let i = 11; i >= 0; i--) {
        const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
        categories.push(d.toLocaleDateString("en-US", { month: "short" }));
        dateKeys.push(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`);
      }
      matchStart       = new Date(now.getFullYear(), now.getMonth() - 11, 1);
      docGroupFormat   = "%Y-%m";
      queryGroupFormat = "%Y-%m";
    }

    const [docAgg, queryAgg] = await Promise.all([
      analyticsSvc.countDocumentsByPeriod(matchStart, docGroupFormat),
      analyticsSvc.countMessagesByPeriod(matchStart, queryGroupFormat),
    ]);

    const docMap   = buildCountMap(docAgg);
    const queryMap = buildCountMap(queryAgg);

    return success(res, {
      categories,
      documents: dateKeys.map((k) => docMap[k] || 0),
      queries:   dateKeys.map((k) => queryMap[k] || 0),
    });
  } catch (err) {
    return systemfailure(res, err);
  }
};

/** Return ISO week number (1–53) for a given date. */
function getISOWeek(date) {
  const d = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
  const dayNum = d.getUTCDay() || 7;
  d.setUTCDate(d.getUTCDate() + 4 - dayNum);
  const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
  return Math.ceil((((d - yearStart) / 86400000) + 1) / 7);
}

// ── GET /dashboard/activity-feed ──────────────────────────────────────────────

exports.getActivityFeed = async (req, res) => {
  try {
    const limit = 20;

    // Recent document uploads
    const recentDocs = await Document.find()
      .sort({ createdAt: -1 })
      .limit(limit)
      .select("filename status createdAt updatedAt")
      .lean();

    // Recent conversations (QA queries)
    const recentConvos = await Conversation.find()
      .sort({ updatedAt: -1 })
      .limit(10)
      .select("title updatedAt messages")
      .lean();

    const activities = [];

    // Map documents to activity items
    for (const doc of recentDocs) {
      if (doc.status === "Completed") {
        activities.push({
          id:        `proc-${doc._id}`,
          type:      "processing",
          text:      `Document processing completed: ${doc.filename}`,
          timestamp: doc.updatedAt,
        });
      } else {
        activities.push({
          id:        `upload-${doc._id}`,
          type:      "upload",
          text:      `${doc.filename} uploaded`,
          timestamp: doc.createdAt,
        });
      }
    }

    // Map conversations to activity items
    for (const convo of recentConvos) {
      const lastMsg = convo.messages?.at(-1);
      if (!lastMsg) continue;
      const question = lastMsg.userMessage
        ? lastMsg.userMessage.length > 60
          ? `${lastMsg.userMessage.slice(0, 60)}…`
          : lastMsg.userMessage
        : convo.title;
      activities.push({
        id:        `qa-${convo._id}`,
        type:      "query",
        text:      `Q&A: "${question}"`,
        timestamp: convo.updatedAt,
      });
    }

    // Sort by newest first and cap at limit
    activities.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));

    return success(res, { activities: activities.slice(0, limit) });
  } catch (err) {
    return systemfailure(res, err);
  }
};

// ── GET /dashboard/recent-queries ─────────────────────────────────────────────

exports.getRecentQueries = async (req, res) => {
  try {
    const isAdmin = ["Admin", "SuperAdmin"].includes(req.user.role);

    const filter = isAdmin ? {} : { userId: req.user._id };

    const convos = await Conversation.find(filter)
      .sort({ updatedAt: -1 })
      .limit(10)
      .select("messages updatedAt");

    const queries = [];

    for (const c of convos) {
      for (let i = c.messages.length - 1; i >= 0 && queries.length < 5; i--) {
        const msg = c.messages[i];
        const minsAgo = Math.round((Date.now() - new Date(msg.createdAt || c.updatedAt).getTime()) / 60000);
        queries.push({
          _id:      msg._id,
          question: msg.userMessage,
          type:     "Retrieval",
          time:     minsAgo < 1 ? "just now" : `${minsAgo}m ago`,
        });
      }
      if (queries.length >= 5) break;
    }

    return success(res, { queries: queries.slice(0, 5) });
  } catch (err) {
    return systemfailure(res, err);
  }
};
