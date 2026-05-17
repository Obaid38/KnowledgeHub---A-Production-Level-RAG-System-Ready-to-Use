// scripts/seedSuperAdmin.js
require("dotenv").config();
const mongoose = require("mongoose");
const User     = require("../src/models/User");
const { loadCompanyProfile } = require("../src/config/companyProfile");

(async () => {
  try {
    await mongoose.connect(process.env.MONGO_URI);
    await User.syncIndexes();
    const companyProfile = loadCompanyProfile();

    const email    = process.env.SUPERADMIN_EMAIL    || companyProfile.contact.seedSuperadminEmail;
    const password = process.env.SUPERADMIN_PASSWORD || "Admin@123456";

    const exists = await User.exists({ email });
    if (exists) {
      console.log(`SuperAdmin already exists: ${email}`);
    } else {
      await User.create({
        firstName:  "Super",
        lastName:   "Admin",
        email,
        password,
        role:       "SuperAdmin",
        verified:   "Verified",
        verifiedAt: new Date(),
      });
      console.log(`SuperAdmin created: ${email}`);
    }
  } catch (err) {
    console.error("Seed failed:", err);
    process.exit(1);
  } finally {
    await mongoose.disconnect();
  }
})();
