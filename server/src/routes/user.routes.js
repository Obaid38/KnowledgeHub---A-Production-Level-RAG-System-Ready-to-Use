// routes/user.routes.js  →  mounted at /users
const router   = require("express").Router();
const ctrl     = require("../controllers/user.controller");
const { auth, admin } = require("../middlewares/auth");
const { formData } = require("../middlewares/upload");

const fd = formData.none();

router.use(auth(), admin);

router.get("/",              ctrl.listUsers);
router.post("/:id/approve",  ctrl.approveUser);
router.post("/:id/reject",   fd, ctrl.rejectUser);
router.patch("/:id/role",    ctrl.updateUserRole);
router.delete("/:id",        ctrl.deleteUser);

module.exports = router;
