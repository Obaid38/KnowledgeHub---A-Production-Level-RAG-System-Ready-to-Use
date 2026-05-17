// utils/otp.js

const config = require("../config");

/**
 * Generate a 6-digit OTP
 * @returns {string} 6-digit OTP string
 */
function generateOTP() {
  return Math.floor(100000 + Math.random() * 900000).toString();
}

/**
 * Generate OTP expiry date
 * @returns {Date} OTP expiry date
 */
function generateOTPExpiry() {
  return new Date(Date.now() + config.otp.expiryMinutes * 60 * 1000);
}

/**
 * Check if OTP has expired
 * @param {Date} otpExpiry - OTP expiry date
 * @returns {boolean} true if expired, false if still valid
 */
function isOTPExpired(otpExpiry) {
  if (!otpExpiry) return true;
  return new Date() > otpExpiry;
}

/**
 * Validate OTP format
 * @param {string} otp - OTP to validate
 * @returns {boolean} true if valid format, false otherwise
 */
function isValidOTPFormat(otp) {
  return /^\d{6}$/.test(otp);
}

module.exports = {
  generateOTP,
  generateOTPExpiry,
  isOTPExpired,
  isValidOTPFormat,
};
