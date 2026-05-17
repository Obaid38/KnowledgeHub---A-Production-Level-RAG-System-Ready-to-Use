'use client';

import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { useLocale, useTranslations } from 'next-intl';
import Image from 'next/image';
import InputField from '../form/input/InputField';
import { useAuthStore } from '@/store/authStore';
import { brandConfig } from "@/config/companyProfile";

const CODE_LENGTH = 6;
const REFRESH_INTERVAL = 30;

const MfaForm: React.FC = () => {
  const router = useRouter();
  const locale = useLocale();
  const t = useTranslations('auth.mfa');
  const { pendingEmail, pendingMfaToken, verifyMfa, verifyMfaRecovery, clearError, isLoading, error } =
    useAuthStore();

  const [digits,       setDigits]       = useState<string[]>(Array(CODE_LENGTH).fill(''));
  const [countdown,    setCountdown]    = useState(REFRESH_INTERVAL);
  const [useRecovery,  setUseRecovery]  = useState(false);
  const [formError,    setFormError]    = useState('');
  const [recoveryCode, setRecoveryCode] = useState('');
  const inputRefs = useRef<(HTMLInputElement | null)[]>([]);

  useEffect(() => {
    if (!pendingEmail || !pendingMfaToken) {
      router.replace(`/${locale}/signin`);
    }
  }, [pendingEmail, pendingMfaToken, locale, router]);

  useEffect(() => {
    const timer = setInterval(() => {
      setCountdown((prev) => {
        if (prev <= 1) {
          setDigits(Array(CODE_LENGTH).fill(''));
          inputRefs.current[0]?.focus();
          return REFRESH_INTERVAL;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  function handleDigitChange(index: number, value: string) {
    const digit = value.replace(/\D/g, '').slice(-1);
    const updated = [...digits];
    updated[index] = digit;
    setDigits(updated);
    if (digit && index < CODE_LENGTH - 1) inputRefs.current[index + 1]?.focus();
  }

  function handleKeyDown(index: number, e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Backspace') {
      if (digits[index]) {
        const updated = [...digits];
        updated[index] = '';
        setDigits(updated);
      } else if (index > 0) {
        inputRefs.current[index - 1]?.focus();
      }
    }
    if (e.key === 'ArrowLeft'  && index > 0)             inputRefs.current[index - 1]?.focus();
    if (e.key === 'ArrowRight' && index < CODE_LENGTH - 1) inputRefs.current[index + 1]?.focus();
  }

  function handlePaste(e: React.ClipboardEvent) {
    e.preventDefault();
    const pasted = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, CODE_LENGTH);
    const updated = Array(CODE_LENGTH).fill('');
    pasted.split('').forEach((char, i) => { updated[i] = char; });
    setDigits(updated);
    inputRefs.current[Math.min(pasted.length, CODE_LENGTH - 1)]?.focus();
  }

  function getPostMfaDest(): string {
    const { user } = useAuthStore.getState();
    const isAdmin = user?.role === 'Admin' || user?.role === 'SuperAdmin';
    return isAdmin ? `/${locale}` : `/${locale}/qa`;
  }

  const onSubmitTotp = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError('');
    clearError();
    try {
      const code = digits.join('');
      if (code.length !== CODE_LENGTH) { setFormError('Please enter a 6-digit code'); return; }
      await verifyMfa(code);
      router.push(getPostMfaDest());
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Invalid code. Please try again.';
      setFormError(errorMessage);
      setDigits(Array(CODE_LENGTH).fill(''));
      inputRefs.current[0]?.focus();
    }
  };

  const onSubmitRecovery = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError('');
    clearError();
    try {
      if (!recoveryCode.trim()) { setFormError('Please enter a recovery code'); return; }
      await verifyMfaRecovery(recoveryCode);
      router.push(getPostMfaDest());
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Invalid recovery code.';
      setFormError(errorMessage);
    }
  };

  const countdownIsLow = countdown <= 10;

  return (
    <div className="auth-card">

      {/* ── Brand ── */}
      <div className="auth-brand">
        <Image
          src={brandConfig.logo_light_path}
          alt={brandConfig.app_name}
          width={72}
          height={40}
          className="dark:hidden"
        />
        <Image
          src={brandConfig.logo_dark_path}
          alt={brandConfig.app_name}
          width={72}
          height={40}
          className="hidden dark:block"
        />
        <div className="auth-brand-divider" />
        <div>
          <p className="text-theme-sm font-semibold text-gray-900 dark:text-white/90">{brandConfig.app_name}</p>
          <p className="text-theme-xs text-gray-400 dark:text-gray-500">{brandConfig.app_tagline}</p>
        </div>
      </div>

      {/* ════════════════════════════════════════
          TOTP view
      ════════════════════════════════════════ */}
      {!useRecovery ? (
        <>
          {/* Shield icon */}
          <div className="flex justify-center mb-5">
            <div className="w-16 h-16 rounded-2xl bg-brand-50 dark:bg-brand-500/10 flex items-center justify-center">
              <svg width="32" height="32" fill="none" stroke="currentColor" viewBox="0 0 24 24"
                className="text-brand-500 dark:text-brand-400">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.6}
                  d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
              </svg>
            </div>
          </div>

          {/* Heading */}
          <div className="text-center mb-6">
            <h2>{t('title')}</h2>
            <p className="mt-1">{t('subtitle')}</p>
            {pendingEmail && (
              <p className="text-theme-xs text-gray-400 dark:text-gray-500 mt-2">
                {t('signingInAs')}{' '}
                <span className="font-semibold text-gray-700 dark:text-gray-300">{pendingEmail}</span>
              </p>
            )}
          </div>

          {/* Countdown ring */}
          <div className="flex items-center justify-center gap-2 mb-6 text-theme-xs text-gray-500 dark:text-gray-400">
            <svg className="w-5 h-5 -rotate-90" viewBox="0 0 20 20">
              <circle
                cx="10" cy="10" r="8" fill="none" stroke="currentColor"
                strokeWidth="2" className="opacity-20"
              />
              <circle
                cx="10" cy="10" r="8" fill="none" strokeWidth="2"
                strokeDasharray={`${2 * Math.PI * 8}`}
                strokeDashoffset={`${2 * Math.PI * 8 * (1 - countdown / REFRESH_INTERVAL)}`}
                className={`transition-all duration-1000 ${
                  countdownIsLow ? 'stroke-error-500' : 'stroke-brand-500'
                }`}
                strokeLinecap="round"
              />
            </svg>
            <span>
              {t('codeRefreshesIn')}{' '}
              <span className={`font-semibold ${
                countdownIsLow
                  ? 'text-error-500 dark:text-error-400'
                  : 'text-brand-500 dark:text-brand-400'
              }`}>
                {countdown}s
              </span>
            </span>
          </div>

          {/* Error */}
          {(formError || error) && (
            <div className="server-error text-center mb-4">{formError || error}</div>
          )}

          {/* Digit inputs */}
          <form onSubmit={onSubmitTotp}>
            <div className="flex justify-center gap-2 sm:gap-3 mb-6" onPaste={handlePaste}>
              {digits.map((digit, i) => (
                <input
                  key={i}
                  ref={(el) => { inputRefs.current[i] = el; }}
                  type="text"
                  inputMode="numeric"
                  maxLength={1}
                  value={digit}
                  onChange={(e) => handleDigitChange(i, e.target.value)}
                  onKeyDown={(e) => handleKeyDown(i, e)}
                  disabled={isLoading}
                  autoFocus={i === 0}
                  className={`w-11 h-14 sm:w-12 text-center text-xl font-bold rounded-xl
                    border-2 transition caret-transparent
                    bg-white dark:bg-gray-800
                    text-gray-900 dark:text-white
                    border-gray-200 dark:border-gray-700
                    focus:outline-none focus:border-brand-500 dark:focus:border-brand-400
                    focus:ring-2 focus:ring-brand-500/10 dark:focus:ring-brand-400/10
                    disabled:opacity-50 disabled:cursor-not-allowed
                    ${digit ? 'border-brand-400 dark:border-brand-500' : ''}
                  `}
                />
              ))}
            </div>

            <button
              type="submit"
              disabled={digits.some((d) => !d) || isLoading}
              className="btn-primary"
            >
              {isLoading ? t('verifyingBtn') : t('verifyBtn')}
            </button>
          </form>

          {/* Divider */}
          <div className="relative flex items-center justify-center my-5">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-gray-200 dark:border-gray-700" />
            </div>
            <span className="relative bg-white dark:bg-gray-800 px-3 text-theme-xs text-gray-400 dark:text-gray-500">
              {t('orUseRecovery')}
            </span>
          </div>

          {/* Switch to recovery */}
          <button
            onClick={() => { setUseRecovery(true); setFormError(''); setRecoveryCode(''); clearError(); }}
            disabled={isLoading}
            className="btn-outline disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {t('useRecoveryBtn')}
          </button>
        </>
      ) : (
        /* ════════════════════════════════════════
           Recovery code view
        ════════════════════════════════════════ */
        <>
          <div className="text-center mb-6">
            <h2>{t('recoveryTitle')}</h2>
            <p className="mt-1">{t('recoverySubtitle')}</p>
          </div>

          {(formError || error) && (
            <div className="server-error text-center mb-4">{formError || error}</div>
          )}

          <form onSubmit={onSubmitRecovery} className="space-y-5">
            <InputField
              label={t('recoveryLabel')}
              placeholder={t('recoveryPlaceholder')}
              value={recoveryCode}
              onChange={(e) => setRecoveryCode(e.target.value)}
              disabled={isLoading}
              className="font-mono tracking-widest text-center"
            />

            <button
              type="submit"
              disabled={isLoading}
              className="btn-primary"
            >
              {isLoading ? t('verifyingBtn') : t('verifyRecoveryBtn')}
            </button>
          </form>
        </>
      )}

      {/* ── Back link ── */}
      <div className="mt-6 text-center">
        <button
          onClick={() => {
            if (useRecovery) {
              setUseRecovery(false);
              setFormError('');
              setRecoveryCode('');
            } else {
              clearError();
              router.push(`/${locale}/signin`);
            }
          }}
          disabled={isLoading}
          className="text-theme-sm text-gray-500 hover:text-gray-800 dark:text-gray-400 dark:hover:text-white/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          ← {useRecovery ? t('backToAuthenticator') : t('backToLogin')}
        </button>
      </div>
    </div>
  );
};

export default MfaForm;
