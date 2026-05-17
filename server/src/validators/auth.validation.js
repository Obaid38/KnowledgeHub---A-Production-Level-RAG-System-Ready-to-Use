// validators/auth.validation.js

const Joi = require("joi");

const login = {
  body: Joi.object({
    email: Joi.string().trim().lowercase().email().required(),
    password: Joi.string().min(6).max(128).required(),
  }),
};

const changePassword = {
  body: Joi.object({
    current_password: Joi.string().min(6).max(128).required(),
    new_password: Joi.string()
      .min(6)
      .max(128)
      .disallow(Joi.ref("current_password"))
      .required(),
  }),
};

const register = {
  body: Joi.object({
    first_name: Joi.string().trim().min(1).max(50).required(),
    last_name: Joi.string().trim().min(1).max(50).required(),
    email: Joi.string().trim().lowercase().email().required(),
    password: Joi.string().min(6).max(128).required(),
    role: Joi.string().valid("user", "admin", "superadmin").default("user"),
  }),
};

const verifyOTP = {
  body: Joi.object({
    email: Joi.string().trim().lowercase().email().required(),
    otp: Joi.string()
      .length(6)
      .pattern(/^\d{6}$/)
      .required(),
  }),
};

const resendOTP = {
  body: Joi.object({
    email: Joi.string().trim().lowercase().email().required(),
  }),
};

const verifyAccount = {
  body: Joi.object({
    email: Joi.string().trim().lowercase().email().required(),
    status: Joi.number().valid(0, 1, 2).optional(),
  }),
};

const forgotPassword = {
  body: Joi.object({
    email: Joi.string().trim().lowercase().email().required(),
  }),
};

const resetPassword = {
  body: Joi.object({
    token: Joi.string()
      .length(64)
      .pattern(/^[a-f0-9]{64}$/)
      .required(),
    new_password: Joi.string().min(6).max(128).required(),
  }),
};

module.exports = {
  login,
  changePassword,
  register,
  verifyOTP,
  verifyAccount,
  forgotPassword,
  resetPassword,
  resendOTP,
};
