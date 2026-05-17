// routes/monitoring.routes.js  →  mounted at /monitoring
const router = require("express").Router();
const ctrl   = require("../controllers/monitoring.controller");
const { auth, admin } = require("../middlewares/auth");

router.use(auth(), admin);

router.get("/resources",    ctrl.getResources);
router.get("/services",     ctrl.getServices);
router.get("/performance",  ctrl.getPerformance);

module.exports = router;
