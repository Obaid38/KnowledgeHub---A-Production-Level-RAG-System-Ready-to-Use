// routes/logs.routes.js  →  mounted at /logs
const router = require("express").Router();
const ctrl   = require("../controllers/logs.controller");
const { auth, admin } = require("../middlewares/auth");

router.use(auth(), admin);

router.get("/",       ctrl.getLogs);       // GET /logs?level=error&limit=50
router.get("/files",  ctrl.getLogFiles);   // GET /logs/files
router.get("/stats",  ctrl.getStats);      // GET /logs/stats?period=daily|weekly|monthly

module.exports = router;
