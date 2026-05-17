// routes/index.js
const router = require("express").Router();

// Health check (public)
router.get("/health", (req, res) => {
  res.status(200).json({
    success: true,
    data: { status: "OK", uptime: process.uptime() },
  });
});

// ── Modules ───────────────────────────────────────────────────────────────────
router.use("/auth",        require("./auth.routes"));
router.use("/users",       require("./user.routes"));
router.use("/rbac",        require("./rbac.routes"));
router.use("/documents",   require("./document.routes"));
router.use("/qa",          require("./qa.routes"));
router.use("/monitoring",  require("./monitoring.routes"));
router.use("/dashboard",   require("./dashboard.routes"));
router.use("/logs",        require("./logs.routes"));

module.exports = router;
