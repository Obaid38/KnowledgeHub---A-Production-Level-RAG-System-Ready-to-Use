// middlewares/logging.js

const expressWinston = require("express-winston");
const { logger } = require("../loaders/logging");
const winston = require("winston");

const requestLogger = expressWinston.logger({
  winstonInstance: logger,
  meta: true,
  msg: (req, res) =>
    `HTTP ${req.method} ${req.url} ${res.statusCode} ${res.responseTime}ms`,
  dynamicMeta: (req) => ({
    requestId: req.id,
    userAgent: req.get("user-agent"),
    ip: req.ip,
  }),
  requestWhitelist: [
    "method",
    "url",
    // exclude authorization header to avoid leaking tokens
    // "headers",
    "httpVersion",
    "originalUrl",
    "query",
    // avoid logging raw body which may include secrets like passwords
    // "body",
  ],
  responseWhitelist: ["statusCode", "responseTime"],
});

const errorLogger = expressWinston.errorLogger({
  winstonInstance: logger,
  format: winston.format.json(),
  dynamicMeta: (req) => ({ requestId: req.id }),
});

module.exports = { requestLogger, errorLogger };
