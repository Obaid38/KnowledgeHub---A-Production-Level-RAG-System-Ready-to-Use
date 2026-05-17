// middlewares/upload.js
// Shared multer instances used across routes.
// - formData : parses multipart/form-data with NO file fields
// - fileUpload: parses multipart/form-data WITH file fields (memory storage)
const multer = require("multer");

const formData  = multer();                                      // .none() — text fields only
const fileUpload = multer({ storage: multer.memoryStorage() }); // .array() / .single() — with files

module.exports = { formData, fileUpload };
