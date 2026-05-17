// validators/system.validation.js

const Joi = require("joi");

// Validation for system status query parameters (if any)
const getComponentStatusValidation = {
  query: Joi.object({
    // Add any query parameters if needed in the future
    include: Joi.string().valid('all', 'critical', 'optional').optional(),
  }),
};

// Validation for performance metrics query parameters
const getPerformanceMetricsValidation = {
  query: Joi.object({
    timeRange: Joi.string().valid('1h', '24h', '7d', '30d').optional(),
    metric: Joi.string().valid('accuracy', 'processing', 'throughput', 'errors', 'all').optional(),
  }),
};

// Validation for system info query parameters
const getSystemInfoValidation = {
  query: Joi.object({
    include: Joi.string().valid('basic', 'detailed', 'all').optional(),
  }),
};

module.exports = {
  getComponentStatusValidation,
  getPerformanceMetricsValidation,
  getSystemInfoValidation,
};
