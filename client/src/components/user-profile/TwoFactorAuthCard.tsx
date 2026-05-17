"use client";
import React, { useState } from "react";
import Modal from "../ui/modal";
import { useModal } from "../../hooks/useModal";
import { useTranslations } from "next-intl";
import { toast } from "react-toastify";
import { RecoveryCodes } from "./RecoveryCodes";
import { useAuthStore } from "@/store/authStore";
import { mfaSetupApi, mfaEnableApi, mfaDisableApi } from "@/services/auth.service";

const STEP_KEYS = ["step1", "step2", "step3", "step4"] as const;

interface MFASetupData {
  secret:  string;
  qrCode:  string;  // base64 data-URL returned by the backend
}

type ModalView = "qr" | "disable" | "codes" | null;

export default function TwoFactorAuthCard() {
  const t    = useTranslations("profile.mfa");
  const tMod = useTranslations("profile.mfa.modal");

  const user              = useAuthStore((s) => s.user);
  const updateUserLocally = useAuthStore((s) => s.updateUserLocally);

  const { isOpen, openModal, closeModal: rawClose } = useModal();

  const [modalView,     setModalView]     = useState<ModalView>(null);
  const [setupData,     setSetupData]     = useState<MFASetupData | null>(null);
  const [recoveryCodes, setRecoveryCodes] = useState<string[]>([]);
  const [otpCode,       setOtpCode]       = useState("");
  const [otpError,      setOtpError]      = useState("");
  const [loading,       setLoading]       = useState(false);
  const [showSecret,    setShowSecret]    = useState(false);
  const [secretCopied,  setSecretCopied]  = useState(false);

  const mfaEnabled = user?.mfaEnabled ?? false;

  const handleClose = () => {
    rawClose();
    setModalView(null);
    setSetupData(null);
    setOtpCode("");
    setOtpError("");
    setShowSecret(false);
    setRecoveryCodes([]);
  };

  // ── Enable flow: step 1 — call /auth/mfa/setup ────────────────────────────
  const handleEnable = async () => {
    setLoading(true);
    try {
      const data = await mfaSetupApi();
      setSetupData({ secret: data.secret, qrCode: data.qrCode });
      setOtpCode("");
      setOtpError("");
      setShowSecret(false);
      setModalView("qr");
      openModal();
    } catch (err: any) {
      toast.error(err?.response?.data?.message ?? tMod("setupError"));
    } finally {
      setLoading(false);
    }
  };

  // ── Enable flow: step 2 — verify TOTP + receive recovery codes ───────────
  const handleVerify = async (e: React.FormEvent) => {
    e.preventDefault();
    if (otpCode.length !== 6) { setOtpError(tMod("codeError")); return; }
    setLoading(true);
    try {
      const res = await mfaEnableApi(otpCode);
      setRecoveryCodes(res.recoveryCodes);
      updateUserLocally({ mfaEnabled: true });
      setModalView("codes");
    } catch (err: any) {
      toast.error(err?.response?.data?.message ?? tMod("verifyError"));
    } finally {
      setLoading(false);
    }
  };

  // ── Disable flow: open confirm modal ─────────────────────────────────────
  const handleOpenDisable = () => {
    setOtpCode("");
    setOtpError("");
    setModalView("disable");
    openModal();
  };

  // ── Disable flow: submit TOTP to /auth/mfa/disable ───────────────────────
  const handleDisable = async (e: React.FormEvent) => {
    e.preventDefault();
    if (otpCode.length !== 6) { setOtpError(tMod("codeError")); return; }
    setLoading(true);
    try {
      const res = await mfaDisableApi(otpCode);
      updateUserLocally({ mfaEnabled: false });
      toast.success(res.message ?? t("disabledMessage"));
      handleClose();
    } catch (err: any) {
      toast.error(err?.response?.data?.message ?? t("disableError"));
    } finally {
      setLoading(false);
    }
  };

  const handleCopySecret = () => {
    if (!setupData?.secret) return;
    navigator.clipboard.writeText(setupData.secret);
    setSecretCopied(true);
    setTimeout(() => setSecretCopied(false), 2000);
  };

  return (
    <>
      <div className="p-5 border border-gray-200 rounded-2xl dark:border-gray-800 lg:p-6">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between mb-5">
          <div>
            <h4 className="mb-1">{t("title")}</h4>
            <p>{t("subtitle")}</p>
          </div>
          <span className={`inline-flex shrink-0 items-center rounded-full px-3 py-1 text-theme-xs font-medium ${
            mfaEnabled
              ? "bg-success-50 text-success-600 dark:bg-success-500/10 dark:text-success-400"
              : "bg-orange-50 text-orange-500 dark:bg-orange-500/10 dark:text-orange-400"
          }`}>
            {mfaEnabled ? t("statusEnabled") : t("statusDisabled")}
          </span>
        </div>

        <ol className="space-y-4 mb-7">
          {STEP_KEYS.map((key, i) => (
            <li key={key} className="flex items-start gap-4">
              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-brand-500 text-theme-xs font-semibold text-white">
                {i + 1}
              </span>
              <div>
                <p className="text-theme-sm font-medium text-gray-800 dark:text-white/90">
                  {t(`steps.${key}Title`)}
                </p>
                <p className="text-theme-xs text-gray-500 dark:text-gray-400 mt-0.5">
                  {t(`steps.${key}Sub`)}
                </p>
              </div>
            </li>
          ))}
        </ol>

        {mfaEnabled ? (
          <button
            onClick={handleOpenDisable}
            disabled={loading}
            className="inline-flex items-center gap-2 rounded-lg border border-error-200 bg-error-50 px-4 py-2.5 text-theme-sm font-semibold text-error-600 hover:bg-error-100 dark:border-error-500/20 dark:bg-error-500/10 dark:text-error-400 dark:hover:bg-error-500/20 transition-colors disabled:opacity-60"
          >
            {loading ? t("disabling") : t("disableButton")}
          </button>
        ) : (
          <button
            onClick={handleEnable}
            disabled={loading}
            className="btn-primary lg:w-auto disabled:opacity-60"
          >
            {loading ? "Loading…" : t("enableButton")}
          </button>
        )}
      </div>

      <Modal
        isOpen={isOpen}
        onClose={modalView === "codes" ? undefined : handleClose}
        showCloseButton={modalView !== "codes"}
      >
        {/* ── QR / verify step ── */}
        {modalView === "qr" && (
          <>
            <div className="pr-10 mb-5">
              <h3 className="mb-1">{tMod("title")}</h3>
              <p>{tMod("subtitle")}</p>
            </div>

            <div className="flex items-center justify-center rounded-xl border border-gray-200 bg-gray-50 dark:border-gray-700 dark:bg-gray-800 p-4 w-44 h-44 mx-auto">
              {setupData?.qrCode ? (
                <img src={setupData.qrCode} alt="TOTP QR code" className="w-full h-full object-contain" />
              ) : (
                <svg viewBox="0 0 40 40" className="w-full h-full text-gray-300 dark:text-gray-600" fill="currentColor">
                  {[0,1,2,3,4,5,6].map((r) =>
                    [0,1,2,3,4,5,6].map((c) => (
                      ((r<3&&c<3)||(r<3&&c>3)||(r>3&&c<3)||(r===3&&c===3)||
                      (r>1&&r<5&&c>1&&c<5&&!(r===2&&c===2)&&!(r===2&&c===4)&&!(r===4&&c===2)&&!(r===4&&c===4)))
                        ? <rect key={`${r}-${c}`} x={c*6} y={r*6} width={5} height={5} rx={0.5} />
                        : null
                    ))
                  )}
                </svg>
              )}
            </div>

            <div className="mt-4">
              <button
                type="button"
                onClick={() => setShowSecret((s) => !s)}
                className="text-theme-xs text-brand-500 hover:text-brand-600 dark:text-brand-400 dark:hover:text-brand-300 transition-colors w-full text-center"
              >
                {showSecret ? tMod("hideSecret") : tMod("cantScan")}
              </button>

              {showSecret && setupData?.secret && (
                <div className="mt-3 rounded-lg border border-gray-200 bg-gray-50 dark:border-gray-700 dark:bg-gray-800 px-4 py-3">
                  <p className="text-theme-xs text-gray-500 dark:text-gray-400 mb-2">
                    {tMod("secretLabel")}
                  </p>
                  <div className="flex items-center gap-2">
                    <code className="flex-1 font-mono text-theme-sm font-semibold tracking-widest text-gray-800 dark:text-white/90 break-all select-all">
                      {setupData.secret}
                    </code>
                    <button
                      type="button"
                      onClick={handleCopySecret}
                      className="shrink-0 rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-theme-xs font-medium text-gray-700 hover:bg-gray-100 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-300 dark:hover:bg-gray-600 transition-colors"
                    >
                      {secretCopied ? tMod("copied") : tMod("copy")}
                    </button>
                  </div>
                </div>
              )}
            </div>

            <form onSubmit={handleVerify} className="mt-5">
              <label className="block mb-1.5">{tMod("codeLabel")}</label>
              <input
                type="text"
                inputMode="numeric"
                maxLength={6}
                value={otpCode}
                onChange={(e) => {
                  setOtpCode(e.target.value.replace(/\D/g, "").slice(0, 6));
                  setOtpError("");
                }}
                placeholder="000000"
                className="form-input text-center tracking-[0.4em] text-lg font-semibold"
              />
              {otpError && <p className="form-error mt-1">{otpError}</p>}

              <div className="flex gap-3 mt-5 justify-end">
                <button type="button" onClick={handleClose} className="btn-outline lg:w-auto">
                  {tMod("cancel")}
                </button>
                <button
                  type="submit"
                  disabled={loading || otpCode.length !== 6}
                  className="btn-primary lg:w-auto disabled:opacity-60"
                >
                  {loading ? tMod("verifying") : tMod("verifyButton")}
                </button>
              </div>
            </form>
          </>
        )}

        {/* ── Disable confirm step ── */}
        {modalView === "disable" && (
          <>
            <div className="pr-10 mb-5">
              <h3 className="mb-1">{t("disableModalTitle")}</h3>
              <p>{t("disableModalSubtitle")}</p>
            </div>

            <form onSubmit={handleDisable} className="mt-5">
              <label className="block mb-1.5">{tMod("codeLabel")}</label>
              <input
                type="text"
                inputMode="numeric"
                maxLength={6}
                value={otpCode}
                onChange={(e) => {
                  setOtpCode(e.target.value.replace(/\D/g, "").slice(0, 6));
                  setOtpError("");
                }}
                placeholder="000000"
                className="form-input text-center tracking-[0.4em] text-lg font-semibold"
              />
              {otpError && <p className="form-error mt-1">{otpError}</p>}

              <div className="flex gap-3 mt-5 justify-end">
                <button type="button" onClick={handleClose} className="btn-outline lg:w-auto">
                  {tMod("cancel")}
                </button>
                <button
                  type="submit"
                  disabled={loading || otpCode.length !== 6}
                  className="inline-flex items-center gap-2 rounded-lg border border-error-200 bg-error-50 px-4 py-2.5 text-theme-sm font-semibold text-error-600 hover:bg-error-100 dark:border-error-500/20 dark:bg-error-500/10 dark:text-error-400 dark:hover:bg-error-500/20 transition-colors disabled:opacity-60"
                >
                  {loading ? t("disabling") : t("disableButton")}
                </button>
              </div>
            </form>
          </>
        )}

        {/* ── Recovery codes step ── */}
        {modalView === "codes" && (
          <RecoveryCodes
            codes={recoveryCodes}
            onDone={() => {
              toast.success(tMod("successMessage"));
              handleClose();
            }}
          />
        )}
      </Modal>
    </>
  );
}
