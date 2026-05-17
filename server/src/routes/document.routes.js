// routes/document.routes.js  →  mounted at /documents
const router   = require("express").Router();
const ctrl     = require("../controllers/document.controller");
const { auth } = require("../middlewares/auth");
const { formData, fileUpload } = require("../middlewares/upload");

const fd = formData.none();

router.use(auth());

// file upload uses fileUpload (memory storage); all others use fd (form-data, no files)
router.post("/upload",      fileUpload.array("files"), ctrl.upload);
router.post("/process",     fd,  ctrl.process);
router.get("/",                  ctrl.list);
router.get("/:id/download",      ctrl.download);
router.get("/:id/preview",       ctrl.preview);
router.patch("/category",   fd,  ctrl.bulkUpdateCategory);
router.delete("/",          fd,  ctrl.bulkDelete);

module.exports = router;
