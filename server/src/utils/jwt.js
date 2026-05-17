// utils/jwt.js
const jwt    = require("jsonwebtoken");
const config = require("../config");

/**
 * Sign a JWT.
 * options.secret     – override default secret (e.g. for MFA tokens)
 * options.expiresIn  – override default TTL
 */
const signJwt = (payload, options = {}) => {
  const secret    = options.secret    || config.jwt.secret;
  const expiresIn = options.expiresIn || config.jwt.expiresIn || "7d";
  if (!secret) throw new Error("JWT secret is not configured");
  return jwt.sign(payload, secret, { expiresIn });
};

/**
 * Verify a JWT.
 * options.secret – override default secret (e.g. for MFA tokens)
 * Throws if invalid or expired.
 */
const verifyJwt = (token, options = {}) => {
  const secret = options.secret || config.jwt.secret;
  if (!secret) throw new Error("JWT secret is not configured");
  return jwt.verify(token, secret);
};

module.exports = { signJwt, verifyJwt };
