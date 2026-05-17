// loaders/logging.js

const winston = require("winston");
const DailyRotateFile = require("winston-daily-rotate-file");
const config = require("../config");

const format = winston.format.combine(
  winston.format.timestamp(),
  winston.format.errors({ stack: true }),
  winston.format.json()
);

const transports = [
  new winston.transports.Console({ level: config.logLevel }),
  new DailyRotateFile({
    dirname: "logs",
    filename: "app-%DATE%.log",
    datePattern: "YYYY-MM-DD",
    level: config.logLevel,
    maxFiles: "14d",
    zippedArchive: true,
  }),
  new DailyRotateFile({
    dirname: "logs",
    filename: "errors-%DATE%.log",
    datePattern: "YYYY-MM-DD",
    level: "error",
    maxFiles: "30d",
    zippedArchive: true,
  }),
];

const logger = winston.createLogger({
  level: config.logLevel,
  format,
  defaultMeta: { service: "api" },
  transports,
});

module.exports = { logger };
