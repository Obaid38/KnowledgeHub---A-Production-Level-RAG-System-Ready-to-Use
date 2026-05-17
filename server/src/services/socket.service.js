// services/socket.service.js
// Socket.IO server — handles real-time document status push to the frontend.
const { Server } = require("socket.io");
const { verifyJwt } = require("../utils/jwt");
const config  = require("../config");
const { logger } = require("../loaders/logging");

/** Singleton Socket.IO server instance. */
let io = null;

/**
 * Attach Socket.IO to the Node HTTP server.
 * Call this once in server.js after creating the httpServer.
 */
function initSocket(httpServer) {
  io = new Server(httpServer, {
    cors: {
      origin: "*",
      methods: ["GET", "POST"],
    },
  });

  // Authenticate every socket connection using the JWT sent in handshake auth.
  io.use((socket, next) => {
    const token = socket.handshake.auth?.token;
    if (!token) return next(new Error("Missing auth token"));
    try {
      const decoded = verifyJwt(token);
      socket.userId = decoded.sub; // MongoDB user _id
      next();
    } catch {
      next(new Error("Invalid or expired auth token"));
    }
  });

  io.on("connection", (socket) => {
    // Put each user in their own room so events are scoped per-user.
    socket.join(`user:${socket.userId}`);
    logger.info(`Socket connected  userId=${socket.userId} id=${socket.id}`);

    socket.on("disconnect", (reason) => {
      logger.info(`Socket disconnected userId=${socket.userId} reason=${reason}`);
    });
  });

  logger.info("Socket.IO ready");
  return io;
}

/**
 * Emit a document status-change event to a specific user.
 * Safe to call even before initSocket() — if io isn't ready yet it's a no-op.
 *
 * @param {string} userId  - MongoDB user _id (string)
 * @param {string} docId   - MongoDB document _id (string)
 * @param {string} status  - "Completed" | "Failed" | "Processing"
 */
function emitDocumentStatus(userId, docId, status) {
  if (!io) return;
  io.to(`user:${userId}`).emit("document:status", { id: docId, status });
  logger.info(`Socket emit document:status → userId=${userId} docId=${docId} status=${status}`);
}

/**
 * Broadcast an activity event to all connected clients.
 * Used to power the real-time Activity Feed on the dashboard.
 *
 * @param {{ id: string, type: string, text: string, timestamp: string }} activity
 */
function emitActivity(activity) {
  if (!io) return;
  io.emit("activity:feed", activity);
}

module.exports = { initSocket, emitDocumentStatus, emitActivity };
