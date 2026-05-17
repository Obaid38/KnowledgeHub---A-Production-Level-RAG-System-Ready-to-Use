// middlewares/errorHandler.js

const {
  systemfailure,
  badRequest,
  requestConflict,
  requestfailure,
} = require("../utils/response");

module.exports = (err, req, res, _next) => {
  // Mongoose / Mongo error mapping
  if (err.name === "ValidationError") {
    return badRequest(res, err.message);
  }
  if (err.name === "CastError") {
    return badRequest(res, `Invalid ${err.path}: ${err.value}`);
  }
  if (err.code === 11000) {
    // duplicate key
    return requestConflict(res, "Duplicate key error");
  }

  // 404s that bubble up intentionally
  if (err.status === 404) {
    return requestfailure(res, err);
  }

  // default 500
  return systemfailure(res, err);
};
