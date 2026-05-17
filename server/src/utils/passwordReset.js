// utils/passwordReset.js

const crypto = require("crypto");
const config = require("../config");

/**
 * Generate a secure password reset token
 * @returns {string} Secure random token
 */
function generateResetToken() {
  return crypto.randomBytes(32).toString("hex");
}

/**
 * Generate password reset token expiry date
 * @returns {Date} Token expiry date
 */
function generateResetTokenExpiry() {
  return new Date(Date.now() + config.passwordReset.expiryMinutes * 60 * 1000);
}

/**
 * Check if password reset token has expired
 * @param {Date} tokenExpiry - Token expiry date
 * @returns {boolean} true if expired, false if still valid
 */
function isResetTokenExpired(tokenExpiry) {
  if (!tokenExpiry) return true;
  return new Date() > tokenExpiry;
}

/**
 * Validate password reset token format
 * @param {string} token - Token to validate
 * @returns {boolean} true if valid format, false otherwise
 */
function isValidResetTokenFormat(token) {
  return /^[a-f0-9]{64}$/.test(token); // 64 character hex string
}

/**
 * Create password reset URL
 * @param {string} token - Reset token
 * @returns {string} Complete reset URL
 */
function createResetUrl(token) {
  return `${config.emailBrand.clientUrl}/auth/reset-password?token=${token}`;
}

/**
 * Hash password reset token for secure storage
 * @param {string} token - Plain text token
 * @returns {string} Hashed token
 */
function hashResetToken(token) {
  return crypto.createHash("sha256").update(token).digest("hex");
}

/**
 * Verify password reset token
 * @param {string} plainToken - Plain text token from URL
 * @param {string} hashedToken - Hashed token from database
 * @returns {boolean} true if tokens match, false otherwise
 */
function verifyResetToken(plainToken, hashedToken) {
  const hashedPlainToken = hashResetToken(plainToken);
  return hashedPlainToken === hashedToken;
}

module.exports = {
  generateResetToken,
  generateResetTokenExpiry,
  isResetTokenExpired,
  isValidResetTokenFormat,
  createResetUrl,
  hashResetToken,
  verifyResetToken,
};
