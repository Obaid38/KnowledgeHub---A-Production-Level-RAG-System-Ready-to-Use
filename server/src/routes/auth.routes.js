// routes/auth.routes.js
const router   = require("express").Router();
const ctrl     = require("../controllers/auth.controller");
const { auth } = require("../middlewares/auth");
const { formData } = require("../middlewares/upload");

const fd = formData.none(); // parse multipart/form-data (no files) on every route

// ── Public ────────────────────────────────────────────────────────────────────
router.post("/register",            fd, ctrl.register);
router.post("/login",               fd, ctrl.login);
router.post("/verify-mfa",          fd, ctrl.verifyMfa);
router.post("/verify-mfa-recovery", fd, ctrl.verifyMfaRecovery);
router.post("/forgot-password",     fd, ctrl.forgotPassword);
router.post("/reset-password",      fd, ctrl.resetPassword);

// ── Authenticated ─────────────────────────────────────────────────────────────
router.get("/me",              auth(),     ctrl.me);
router.patch("/me",            auth(), fd, ctrl.updateProfile);
router.post("/change-password", auth(), fd, ctrl.changePassword);

// ── Authenticated — MFA management ───────────────────────────────────────────
router.post("/mfa/setup",   auth(),     ctrl.mfaSetup);
router.post("/mfa/enable",  auth(), fd, ctrl.mfaEnable);
router.post("/mfa/disable", auth(), fd, ctrl.mfaDisable);

module.exports = router;
