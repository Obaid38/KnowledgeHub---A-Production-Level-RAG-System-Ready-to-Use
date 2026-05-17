// routes/qa.routes.js  →  mounted at /qa
const router   = require("express").Router();
const ctrl     = require("../controllers/qa.controller");
const { auth } = require("../middlewares/auth");
const { formData } = require("../middlewares/upload");

const fd = formData.none();

router.use(auth());

router.post("/query",                   fd, ctrl.query);
router.get("/conversations",                ctrl.listConversations);
router.get("/conversations/:id",            ctrl.getConversation);
router.delete("/conversations/:id",         ctrl.deleteConversation);
router.post("/messages/:id/feedback",   fd, ctrl.submitFeedback);
router.post("/messages/:id/regenerate",     ctrl.regenerate);

module.exports = router;
