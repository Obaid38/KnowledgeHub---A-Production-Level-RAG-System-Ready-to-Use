// routes/rbac.routes.js  →  mounted at /rbac
const router   = require("express").Router();
const ctrl     = require("../controllers/rbac.controller");
const { auth, admin } = require("../middlewares/auth");
const { formData } = require("../middlewares/upload");

const fd = formData.none();

router.use(auth(), admin);

// ── Role management ───────────────────────────────────────────────────────────
router.get("/roles",                       ctrl.listRoles);
router.post("/roles",             fd,      ctrl.createRole);
router.delete("/roles/:role",              ctrl.deleteRole);

// ── Permission matrix + stats per role ───────────────────────────────────────
router.get("/roles/:role/stats",             ctrl.getRoleStats);
router.get("/roles/:role/permissions",       ctrl.getPermissions);
router.put("/roles/:role/permissions", fd,   ctrl.savePermissions);

// ── Metrics ───────────────────────────────────────────────────────────────────
router.get("/metrics",                      ctrl.getMetrics);

module.exports = router;
