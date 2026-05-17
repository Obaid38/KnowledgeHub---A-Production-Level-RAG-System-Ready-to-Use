// validators/user.validation.js

const Joi = require("joi");

const listUsers = {
  query: Joi.object({
    page: Joi.number().integer().min(1).optional(),
    limit: Joi.number().integer().min(1).max(100).optional(),
    status: Joi.string().valid("0", "1", "2").optional(),
  }),
};

module.exports = { listUsers };
