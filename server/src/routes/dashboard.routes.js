// routes/dashboard.routes.js  →  mounted at /dashboard
const router = require("express").Router();
const ctrl   = require("../controllers/dashboard.controller");
const { auth } = require("../middlewares/auth");

router.use(auth());

router.get("/metrics",        ctrl.getMetrics);
router.get("/recent-queries", ctrl.getRecentQueries);
router.get("/query-volume",   ctrl.getQueryVolume);
router.get("/activity-feed",  ctrl.getActivityFeed);

module.exports = router;
