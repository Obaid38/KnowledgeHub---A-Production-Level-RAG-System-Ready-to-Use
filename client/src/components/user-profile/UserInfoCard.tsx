"use client";
import React, { useEffect } from "react";
import { useForm } from "react-hook-form";
import { toast } from "react-toastify";
import { useModal } from "../../hooks/useModal";
import Modal from "../ui/modal";
import Button from "../ui/button/Button";
import InputField from "../form/input/InputField";
import { useAuthStore } from "@/store/authStore";
import { updateProfileApi } from "@/services/auth.service";

interface EditProfileForm {
  firstName: string;
  lastName:  string;
}

export default function UserInfoCard() {
  const { isOpen, openModal, closeModal } = useModal();

  const user              = useAuthStore((s) => s.user);
  const updateUserLocally = useAuthStore((s) => s.updateUserLocally);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<EditProfileForm>({
    defaultValues: {
      firstName: user?.firstName ?? "",
      lastName:  user?.lastName  ?? "",
    },
  });

  // Keep form in sync if the user object changes externally
  useEffect(() => {
    reset({
      firstName: user?.firstName ?? "",
      lastName:  user?.lastName  ?? "",
    });
  }, [user, reset]);

  const onSubmit = async (values: EditProfileForm) => {
    try {
      const updated = await updateProfileApi(values);
      // Update Zustand store locally — no extra API call needed
      updateUserLocally({
        firstName: updated.firstName,
        lastName:  updated.lastName,
      });
      toast.success("Profile updated successfully.");
      closeModal();
    } catch (err: any) {
      toast.error(err?.response?.data?.message ?? "Failed to update profile.");
    }
  };

  const infoFields = [
    { label: "First Name",    value: user?.firstName ?? "—" },
    { label: "Last Name",     value: user?.lastName  ?? "—" },
    { label: "Email address", value: user?.email     ?? "—" },
    { label: "Role",          value: user?.role      ?? "—" },
  ];

  return (
    <div className="p-5 border border-gray-200 rounded-2xl dark:border-gray-800 lg:p-6">
      <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
        <div className="flex-1">
          <h4 className="mb-6">Personal Information</h4>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 lg:gap-7 2xl:gap-x-32">
            {infoFields.map(({ label, value }) => (
              <div key={label}>
                <p className="mb-1 text-theme-xs text-gray-500 dark:text-gray-400">{label}</p>
                <p className="text-theme-sm font-medium text-gray-800 dark:text-white/90">{value}</p>
              </div>
            ))}
          </div>
        </div>

        <button
          onClick={openModal}
          className="flex w-full items-center justify-center gap-2 rounded-full border border-gray-300 bg-white px-4 py-3 text-theme-sm font-medium text-gray-700 shadow-theme-xs hover:bg-gray-50 hover:text-gray-800 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-400 dark:hover:bg-white/[0.03] dark:hover:text-gray-200 lg:inline-flex lg:w-auto transition-colors"
        >
          <svg className="fill-current" width="18" height="18" viewBox="0 0 18 18" fill="none">
            <path fillRule="evenodd" clipRule="evenodd" d="M15.0911 2.78206C14.2125 1.90338 12.7878 1.90338 11.9092 2.78206L4.57524 10.116C4.26682 10.4244 4.0547 10.8158 3.96468 11.2426L3.31231 14.3352C3.25997 14.5833 3.33653 14.841 3.51583 15.0203C3.69512 15.1996 3.95286 15.2761 4.20096 15.2238L7.29355 14.5714C7.72031 14.4814 8.11172 14.2693 8.42013 13.9609L15.7541 6.62695C16.6327 5.74827 16.6327 4.32365 15.7541 3.44497L15.0911 2.78206ZM12.9698 3.84272C13.2627 3.54982 13.7376 3.54982 14.0305 3.84272L14.6934 4.50563C14.9863 4.79852 14.9863 5.2734 14.6934 5.56629L14.044 6.21573L12.3204 4.49215L12.9698 3.84272ZM11.2597 5.55281L5.6359 11.1766C5.53309 11.2794 5.46238 11.4099 5.43238 11.5522L5.01758 13.5185L6.98394 13.1037C7.1262 13.0737 7.25666 13.003 7.35947 12.9002L12.9833 7.27639L11.2597 5.55281Z" fill="" />
          </svg>
          Edit
        </button>
      </div>

      <Modal isOpen={isOpen} onClose={closeModal}>
        <div className="px-2 pr-14">
          <h3 className="mb-2">Edit Personal Information</h3>
          <p className="mb-6 lg:mb-7">Update your details to keep your profile up-to-date.</p>
        </div>
        <form onSubmit={handleSubmit(onSubmit)} noValidate className="flex flex-col">
          <div className="custom-scrollbar h-auto overflow-y-auto px-2 pb-3">
            <div className="grid grid-cols-1 gap-x-6 gap-y-5 lg:grid-cols-2">
              <InputField
                label="First Name"
                type="text"
                error={errors.firstName?.message}
                {...register("firstName", { required: "First name is required." })}
              />
              <InputField
                label="Last Name"
                type="text"
                error={errors.lastName?.message}
                {...register("lastName", { required: "Last name is required." })}
              />
            </div>
          </div>
          <div className="flex items-center gap-3 px-2 mt-6 lg:justify-end">
            <Button size="sm" variant="outline" onClick={closeModal} type="button">
              Close
            </Button>
            <Button size="sm" type="submit" disabled={isSubmitting}>
              {isSubmitting ? "Saving…" : "Save Changes"}
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
