// controllers/logs.controller.js
const fs      = require("fs");
const path    = require("path");
const readline = require("readline");
const logSvc  = require("../services/log.service");
const { success, systemfailure } = require("../utils/response");

const LOGS_DIR = path.join(__dirname, "../../logs");

// ── GET /logs  ─────────────────────────────────────────────────────────────────
// Query: level, search, limit, offset, file (filename, defaults to today)

exports.getLogs = async (req, res) => {
  try {
    const { level, search, limit = 100, offset = 0, file } = req.query;

    const filePath = file
      ? path.join(LOGS_DIR, path.basename(file)) // prevent path traversal
      : null;

    const result = await logSvc.readLogs({
      level,
      search,
      limit:  Number(limit),
      offset: Number(offset),
      file:   filePath,
    });

    return success(res, result);
  } catch (err) {
    return systemfailure(res, err);
  }
};

// ── GET /logs/files  ──────────────────────────────────────────────────────────

exports.getLogFiles = (req, res) => {
  try {
    const files = logSvc.getLogFiles().map((f) => ({
      name: f.name,
      size: f.size,
      mtime: f.mtime,
    }));
    return success(res, { files });
  } catch (err) {
    return systemfailure(res, err);
  }
};

// ── GET /logs/stats?period=daily|weekly|monthly ────────────────────────────────

exports.getStats = async (req, res) => {
  try {
    const { period = "daily" } = req.query;

    const now    = new Date();
    let startDate;

    if (period === "weekly") {
      startDate = new Date(now.getTime() - 7 * 86400000);
    } else if (period === "monthly") {
      startDate = new Date(now.getFullYear(), now.getMonth() - 1, now.getDate());
    } else {
      // daily — today's log file
      startDate = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    }

    // Collect stats across all relevant log files
    const files = logSvc.getLogFiles().filter(
      (f) => new Date(f.mtime) >= startDate
    );

    const combined = {
      total:     0,
      byLevel:   { error: 0, warn: 0, info: 0, http: 0, debug: 0 },
      byHour:    {},  // { "YYYY-MM-DDTHH": count }
      errors:    [],  // last 20 error entries
    };

    for (const f of files) {
      if (!fs.existsSync(f.path)) continue;
      const fileStream = fs.createReadStream(f.path, { encoding: "utf8" });
      const rl = readline.createInterface({ input: fileStream, crlfDelay: Infinity });

      for await (const line of rl) {
        if (!line.trim()) continue;
        let entry;
        try { entry = JSON.parse(line); } catch { continue; }

        const ts = entry.timestamp ? new Date(entry.timestamp) : new Date();
        if (ts < startDate) continue;

        combined.total++;

        const lvl = (entry.level || "info").toLowerCase();
        combined.byLevel[lvl] = (combined.byLevel[lvl] || 0) + 1;

        // Bucket by hour
        const hourKey = ts.toISOString().slice(0, 13); // "YYYY-MM-DDTHH"
        combined.byHour[hourKey] = (combined.byHour[hourKey] || 0) + 1;

        if (lvl === "error" && combined.errors.length < 20) {
          combined.errors.push({
            timestamp: ts.toISOString(),
            message:   entry.message || "",
            stack:     entry.stack   || null,
          });
        }
      }
    }

    // Convert byHour map to sorted array for charting
    const timeline = Object.entries(combined.byHour)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([hour, count]) => ({ hour, count }));

    return success(res, {
      period,
      from:     startDate.toISOString(),
      to:       now.toISOString(),
      total:    combined.total,
      byLevel:  combined.byLevel,
      timeline,
      recentErrors: combined.errors,
    });
  } catch (err) {
    return systemfailure(res, err);
  }
};
