"use client";
import React from "react";
import { useForm } from "react-hook-form";
import { useTranslations } from "next-intl";
import { toast } from "react-toastify";
import InputField from "@/components/form/input/InputField";
import { changePasswordApi } from "@/services/auth.service";

interface ChangePasswordFormValues {
  currentPassword: string;
  newPassword:     string;
  confirmPassword: string;
}

export default function ChangePasswordCard() {
  const t = useTranslations("profile.password");

  const {
    register,
    handleSubmit,
    watch,
    reset,  
    formState: { errors, isSubmitting },
  } = useForm<ChangePasswordFormValues>({
    defaultValues: {
      currentPassword: "",
      newPassword:     "",
      confirmPassword: "",
    },
  });

  const newPasswordValue = watch("newPassword");

  const onSubmit = async (data: ChangePasswordFormValues) => {
    try {
      const res = await changePasswordApi({
        currentPassword: data.currentPassword,
        newPassword:     data.newPassword,
      });

      console.log("Password change response:", res);
      toast.success(res.message ?? t("successMessage"));
      reset();
    } catch (err: any) {
      console.error("Password change error:", err.message);
      const apiMessage = err?.message ?? t("serverError");
      toast.error(apiMessage);
    }
  };

  return (
    <div className="p-5 border border-gray-200 rounded-2xl dark:border-gray-800 lg:p-6">
      <h4 className="mb-1">{t("title")}</h4>
      <p className="mb-6">{t("subtitle")}</p>

      <form onSubmit={handleSubmit(onSubmit)} noValidate>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3 lg:gap-6 mb-6">

          <InputField
            label={t("currentPassword")}
            type="password"
            showPasswordToggle
            placeholder="············"
            error={errors.currentPassword?.message}
            {...register("currentPassword", {
              required: t("validation.currentRequired"),
            })}
          />

          <InputField
            label={t("newPassword")}
            type="password"
            showPasswordToggle
            placeholder="············"
            hint={t("validation.passwordHint")}
            error={errors.newPassword?.message}
            {...register("newPassword", {
              required: t("validation.newRequired"),
              minLength: {
                value:   8,
                message: t("validation.minLength"),
              },
              validate: (val) =>
                val !== watch("currentPassword") || t("validation.sameAsCurrent"),
            })}
          />

          <InputField
            label={t("confirmPassword")}
            type="password"
            showPasswordToggle
            placeholder="············"
            error={errors.confirmPassword?.message}
            {...register("confirmPassword", {
              required: t("validation.confirmRequired"),
              validate: (val) =>
                val === newPasswordValue || t("validation.mismatch"),
            })}
          />
        </div>

        <button
          type="submit"
          disabled={isSubmitting}
          className="btn-primary lg:w-auto disabled:opacity-60"
        >
          {isSubmitting ? t("updating") : t("updateButton")}
        </button>
      </form>
    </div>
  );
}
