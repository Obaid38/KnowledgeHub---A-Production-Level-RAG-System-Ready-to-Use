// scripts/generateTestLogs.js

require("dotenv").config();
const { logger } = require("../src/loaders/logging");

const services = ["backend", "ai"];
const levels = ["info", "warn", "error"];
const messages = [
  "Database connection established",
  "API request received",
  "Processing workflow step",
  "Cache hit for key",
  "User authentication successful",
  "File upload completed",
  "Email sent successfully",
  "Validation passed",
  "Connection timeout",
  "Invalid request parameters",
  "Database query slow",
  "Memory usage high",
  "Failed to connect to external service",
  "Unauthorized access attempt",
  "Database connection lost",
  "Critical system error",
];

function randomItem(array) {
  return array[Math.floor(Math.random() * array.length)];
}

function generateLog() {
  const level = randomItem(levels);
  const service = randomItem(services);
  const message = randomItem(messages);

  const logData = {
    message,
    service,
    requestId: `req-${Math.random().toString(36).substr(2, 9)}`,
  };

  // Add error details for error level logs
  if (level === "error") {
    logData.error = "Error details: " + message;
    logData.stack = `Error: ${message}\n    at Object.<anonymous> (/app/server.js:123:45)\n    at Module._compile (internal/modules/cjs/loader.js:1137:30)`;
  }

  // Add metadata
  logData.meta = {
    userId: Math.floor(Math.random() * 1000),
    duration: Math.floor(Math.random() * 1000),
  };

  // Log with appropriate level
  logger[level](logData);
}

function startGenerating() {
  console.log("Starting log generation...");
  console.log("Press Ctrl+C to stop");

  // Generate initial batch
  for (let i = 0; i < 50; i++) {
    generateLog();
  }

  // Generate logs every 2-5 seconds
  setInterval(() => {
    const count = Math.floor(Math.random() * 3) + 1;
    for (let i = 0; i < count; i++) {
      generateLog();
    }
  }, Math.random() * 3000 + 2000);
}

// Handle graceful shutdown
process.on("SIGINT", () => {
  console.log("\nStopping log generation...");
  process.exit(0);
});

startGenerating();
