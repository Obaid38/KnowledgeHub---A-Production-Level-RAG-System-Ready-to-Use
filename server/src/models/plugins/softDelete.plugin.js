// models/plugins/softDelete.plugin.js

// Reusable soft-delete plugin: adds deleted_at and hides soft-deleted docs by default
module.exports = function softDeletePlugin(schema) {
  schema.add({ deleted_at: { type: Date, default: null } });

  const autoFilter = function (next) {
    if (!this.getOptions || !this.getOptions().withDeleted) {
      this.where({ deleted_at: null });
    }
    next();
  };

  schema.pre("find", autoFilter);
  schema.pre("findOne", autoFilter);
  schema.pre("countDocuments", autoFilter);
  schema.pre("findOneAndUpdate", autoFilter);

  schema.pre("aggregate", function (next) {
    const withDeleted = this.options?.withDeleted;
    const hasDeletedMatch = this.pipeline().some(
      (s) =>
        s.$match && Object.prototype.hasOwnProperty.call(s.$match, "deleted_at")
    );
    if (!withDeleted && !hasDeletedMatch) {
      this.pipeline().unshift({ $match: { deleted_at: null } });
    }
    next();
  });

  schema.methods.softDelete = function () {
    this.deleted_at = new Date();
    return this.save();
  };

  schema.statics.restoreById = function (id) {
    return this.findByIdAndUpdate(
      id,
      { $set: { deleted_at: null } },
      { new: true }
    );
  };
};
