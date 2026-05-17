// services/log.service.js

const fs = require("fs");
const path = require("path");
const readline = require("readline");
const { logger } = require("../loaders/logging");

class LogService {
  constructor() {
    this.logsDir = path.join(__dirname, "../../logs");
  }

  /**
   * Get all log files sorted by date (newest first)
   */
  getLogFiles() {
    try {
      if (!fs.existsSync(this.logsDir)) {
        return [];
      }

      const files = fs.readdirSync(this.logsDir);
      const logFiles = files
        .filter((file) => file.startsWith("app-") && file.endsWith(".log"))
        .map((file) => {
          const stats = fs.statSync(path.join(this.logsDir, file));
          return {
            name: file,
            path: path.join(this.logsDir, file),
            mtime: stats.mtime,
            size: stats.size,
          };
        })
        .sort((a, b) => b.mtime - a.mtime);

      return logFiles;
    } catch (error) {
      logger.error({
        message: "Error getting log files",
        error: error.message,
      });
      return [];
    }
  }

  /**
   * Get the most recent log file
   */
  getCurrentLogFile() {
    const files = this.getLogFiles();
    return files.length > 0 ? files[0].path : null;
  }

  /**
   * Parse a log line into structured data
   */
  parseLogLine(line) {
    try {
      // Try parsing as JSON first (winston JSON format)
      const log = JSON.parse(line);
      return {
        timestamp: log.timestamp || new Date().toISOString(),
        level: log.level || "info",
        message: log.message || "",
        service: log.service || "backend",
        meta: log.meta || {},
        requestId: log.requestId || null,
        error: log.error || null,
        stack: log.stack || null,
      };
    } catch (error) {
      // Fallback for non-JSON lines
      return {
        timestamp: new Date().toISOString(),
        level: "info",
        message: line,
        service: "backend",
        meta: {},
        requestId: null,
        error: null,
        stack: null,
      };
    }
  }

  /**
   * Read logs from a file with filters
   */
  async readLogs(options = {}) {
    const {
      level = null,
      service = null,
      search = null,
      limit = 100,
      offset = 0,
      file = null,
    } = options;

    try {
      const logFile = file || this.getCurrentLogFile();
      if (!logFile || !fs.existsSync(logFile)) {
        return { logs: [], total: 0, hasMore: false };
      }

      const logs = [];
      const fileStream = fs.createReadStream(logFile, { encoding: "utf8" });
      const rl = readline.createInterface({
        input: fileStream,
        crlfDelay: Infinity,
      });

      const allLogs = [];
      for await (const line of rl) {
        if (line.trim()) {
          const log = this.parseLogLine(line);
          allLogs.push(log);
        }
      }

      // Reverse to get newest first
      allLogs.reverse();

      // Apply filters
      let filteredLogs = allLogs;

      if (level) {
        filteredLogs = filteredLogs.filter((log) => log.level === level);
      }

      if (service) {
        filteredLogs = filteredLogs.filter((log) => log.service === service);
      }

      if (search) {
        const searchLower = search.toLowerCase();
        filteredLogs = filteredLogs.filter(
          (log) =>
            log.message.toLowerCase().includes(searchLower) ||
            (log.error && log.error.toLowerCase().includes(searchLower)) ||
            (log.stack && log.stack.toLowerCase().includes(searchLower))
        );
      }

      const total = filteredLogs.length;
      const paginatedLogs = filteredLogs.slice(offset, offset + limit);
      const hasMore = offset + limit < total;

      return {
        logs: paginatedLogs,
        total,
        hasMore,
        file: path.basename(logFile),
      };
    } catch (error) {
      logger.error({ message: "Error reading logs", error: error.message });
      throw error;
    }
  }

  /**
   * Watch log file for changes and stream new logs
   */
  watchLogs(callback, filters = {}) {
    const logFile = this.getCurrentLogFile();
    if (!logFile || !fs.existsSync(logFile)) {
      return null;
    }

    let lastSize = fs.statSync(logFile).size;
    let isReading = false;

    const watcher = fs.watch(logFile, async (eventType) => {
      if (eventType === "change" && !isReading) {
        isReading = true;
        try {
          const stats = fs.statSync(logFile);
          const newSize = stats.size;

          if (newSize > lastSize) {
            const stream = fs.createReadStream(logFile, {
              start: lastSize,
              end: newSize,
              encoding: "utf8",
            });

            const rl = readline.createInterface({
              input: stream,
              crlfDelay: Infinity,
            });

            for await (const line of rl) {
              if (line.trim()) {
                const log = this.parseLogLine(line);

                // Apply filters
                let shouldEmit = true;
                if (filters.level && log.level !== filters.level) {
                  shouldEmit = false;
                }
                if (filters.service && log.service !== filters.service) {
                  shouldEmit = false;
                }
                if (filters.search) {
                  const searchLower = filters.search.toLowerCase();
                  if (
                    !log.message.toLowerCase().includes(searchLower) &&
                    !(
                      log.error && log.error.toLowerCase().includes(searchLower)
                    ) &&
                    !(
                      log.stack && log.stack.toLowerCase().includes(searchLower)
                    )
                  ) {
                    shouldEmit = false;
                  }
                }

                if (shouldEmit) {
                  callback(log);
                }
              }
            }

            lastSize = newSize;
          }
        } catch (error) {
          logger.error({
            message: "Error watching logs",
            error: error.message,
          });
        } finally {
          isReading = false;
        }
      }
    });

    return watcher;
  }

  /**
   * Get log statistics
   */
  async getLogStats(file = null) {
    try {
      const logFile = file || this.getCurrentLogFile();
      if (!logFile || !fs.existsSync(logFile)) {
        return {
          total: 0,
          byLevel: {},
          byService: {},
        };
      }

      const fileStream = fs.createReadStream(logFile, { encoding: "utf8" });
      const rl = readline.createInterface({
        input: fileStream,
        crlfDelay: Infinity,
      });

      const stats = {
        total: 0,
        byLevel: {},
        byService: {},
      };

      for await (const line of rl) {
        if (line.trim()) {
          const log = this.parseLogLine(line);
          stats.total++;
          stats.byLevel[log.level] = (stats.byLevel[log.level] || 0) + 1;
          stats.byService[log.service] =
            (stats.byService[log.service] || 0) + 1;
        }
      }

      return stats;
    } catch (error) {
      logger.error({
        message: "Error getting log stats",
        error: error.message,
      });
      throw error;
    }
  }
}

// Create singleton instance
const logService = new LogService();

module.exports = logService;
