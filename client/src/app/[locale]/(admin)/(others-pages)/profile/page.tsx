import UserInfoCard       from "@/components/user-profile/UserInfoCard";
import UserMetaCard       from "@/components/user-profile/UserMetaCard";
import ChangePasswordCard from "@/components/user-profile/ChangePasswordCard";
import TwoFactorAuthCard from "@/components/user-profile/TwoFactorAuthCard";
import { Metadata } from "next";

export const metadata: Metadata = {
  title: "Profile | Dashboard",
  description: "Manage your profile, password, and security settings.",
};

export default function Profile() {
  return (
    <div>
      <div className="rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03] lg:p-6">
        <h3 className="mb-5 lg:mb-7">Profile</h3>

        <div className="space-y-6">
          {/* 1. Avatar + social links */}
          <UserMetaCard />

          {/* 2. Personal info */}
          <UserInfoCard />

          {/* 3. Change password */}
          <ChangePasswordCard />

          {/* 4. Two-factor authentication */}
          <TwoFactorAuthCard />
        </div>
      </div>
    </div>
  );
}