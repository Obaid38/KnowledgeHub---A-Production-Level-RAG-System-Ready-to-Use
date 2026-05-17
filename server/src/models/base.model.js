// models/base.model.js

const { Schema } = require("mongoose");
const softDeletePlugin = require("./plugins/softDelete.plugin");

// Build a schema with consistent timestamps (+ optional soft delete)
const buildSchema = (
  definition,
  {
    softDelete = true,
    timestamps = { createdAt: "created_at", updatedAt: "updated_at" },
  } = {}
) => {
  const schema = new Schema(definition, { timestamps });
  if (softDelete) schema.plugin(softDeletePlugin);
  return schema;
};

module.exports = { buildSchema };
