// utils/response.js — Spec-compliant response helpers
// Success: { success: true, data: {...} }
// Error:   { success: false, error: { code, message } }

const { logger } = require("../loaders/logging");
const { sendErrorAlert } = require("./emailSender");

const apiSuccess = (res, data = null, statusCode = 200) =>
  res.status(statusCode).json({ success: true, data });

const apiError = (res, code, message, statusCode = 400) =>
  res.status(statusCode).json({ success: false, error: { code, message } });

// ── Convenience wrappers ──────────────────────────────────────────────────────

const success = (res, data) => apiSuccess(res, data, 200);
const created = (res, data) => apiSuccess(res, data, 201);

const badRequest = (res, message = "Bad request", code = "VALIDATION_ERROR") =>
  apiError(res, code, message, 400);

const unauthorized = (res, message = "Missing or invalid token", code = "UNAUTHORIZED") =>
  apiError(res, code, message, 401);

const forbidden = (res, message = "Insufficient role", code = "FORBIDDEN") =>
  apiError(res, code, message, 403);

const notFound = (res, message = "Resource not found", code = "NOT_FOUND") =>
  apiError(res, code, message, 404);

const requestConflict = (res, message = "Conflict", code = "CONFLICT") =>
  apiError(res, code, message, 409);

const systemfailure = (res, err) => {
  const message =
    process.env.NODE_ENV === "production"
      ? "Unexpected error"
      : (err?.message || "Unexpected error");

  logger.error({
    message: err?.message || "System failure",
    type: "systemfailure",
    stack: err?.stack || null,
  });

  if (
    ["MongooseServerSelectionError", "MongoNetworkError", "MongoTimeoutError"].includes(
      err?.name
    ) &&
    process.env.APP_ENV === "production"
  ) {
    sendErrorAlert("🚨 MongoDB Connection Error", `${err?.name}\n\n${err?.stack || ""}`);
  }

  return apiError(res, "INTERNAL_ERROR", message, 500);
};

// Legacy aliases kept for any remaining callers
const requestfailure = (res, err) => systemfailure(res, err);

module.exports = {
  apiSuccess,
  apiError,
  success,
  created,
  badRequest,
  unauthorized,
  forbidden,
  notFound,
  requestConflict,
  systemfailure,
  requestfailure,
};
