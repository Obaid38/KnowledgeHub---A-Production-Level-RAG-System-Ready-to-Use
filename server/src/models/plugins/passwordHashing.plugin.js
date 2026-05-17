// models/plugins/passwordHashing.plugin.js

// Generic hashing plugin for any field (defaults to 'password')
module.exports = function passwordHashingPlugin(
  schema,
  { field = "password", hash } = {}
) {
  if (typeof hash !== "function") {
    throw new Error("passwordHashingPlugin requires a hash function");
  }

  // Hash on create/save
  schema.pre("save", async function (next) {
    if (!this.isModified(field)) return next();
    this[field] = await hash(this[field]);
    next();
  });

  // Hash on findOneAndUpdate (PATCH/PUT)
  schema.pre("findOneAndUpdate", async function (next) {
    const update = this.getUpdate() || {};
    const $set = update.$set || update;

    if ($set[field]) {
      $set[field] = await hash($set[field]);
      if (update.$set) update.$set = $set;
      else Object.assign(update, $set);
    }
    next();
  });
};
