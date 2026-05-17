'use client';

import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import { useRouter } from 'next/navigation';
import { useLocale, useTranslations } from 'next-intl';
import Link from 'next/link';
import { ChevronLeft } from 'lucide-react';
import InputField from '../form/input/InputField';
import Logo from '../common/Logo';
import { useAuthStore } from '@/store/authStore';

const forgotPasswordSchema = z.object({
  email: z.string().email('Invalid email').nonempty('Email is required'),
});

type ForgotPasswordFormData = z.infer<typeof forgotPasswordSchema>;

const ForgotPasswordForm: React.FC = () => {
  const router = useRouter();
  const locale = useLocale();
  const t = useTranslations('auth.forgotPassword');
  const { forgotPassword, isLoading, error, clearError } = useAuthStore();
  const [formError, setFormError] = useState('');
  const [successMessage, setSuccessMessage] = useState('');

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ForgotPasswordFormData>({
    resolver: zodResolver(forgotPasswordSchema),
  });

 const onSubmit = async (values: ForgotPasswordFormData) => {
    setFormError('');
    setSuccessMessage('');
    clearError();
    try {
      await forgotPassword({ email: values.email });
      setSuccessMessage(t('successMessage'));
      setTimeout(() => { router.push(`/${locale}/signin`); }, 3000);
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : 'Failed to send reset link. Please try again.';
      setFormError(errorMessage);
    }
  };

  return (
    <div className="auth-card">

      {/* ── Back button ── */}
      <button
        onClick={() => router.push(`/${locale}/signin`)}
        className="flex items-center gap-1.5 text-theme-sm font-medium text-gray-500 hover:text-gray-800 dark:text-gray-400 dark:hover:text-white/90 transition-colors mb-6"
      >
        <ChevronLeft size={16} />
        {t('backToLogin')}
      </button>

      {/* ── Brand ── */}
      <Logo/>

      {/* ── Heading ── */}
      <div className="mb-6 text-center">
        <h2>{t('title')}</h2>
        <p className="mt-1">{t('subtitle')}</p>
      </div>

      {/* ── Error ── */}
      {formError && (
        <div className="server-error">{formError}</div>
      )}

      {/* ── Success ── */}
      {successMessage && (
        <div className="mb-4 px-4 py-3 rounded-lg bg-success-50 dark:bg-success-500/10 border border-success-100 dark:border-success-500/20 text-theme-sm text-success-600 dark:text-success-400">
          {successMessage}
        </div>
      )}

      {/* ── Form ── */}
      {!successMessage && (
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
          <InputField
            label={t('emailLabel')}
            type="email"
            placeholder={t('emailPlaceholder')}
            {...register('email')}
            error={errors.email?.message}
            disabled={isLoading}
          />

          <button
            type="submit"
            disabled={isLoading}
            className="btn-primary"
          >
            {isLoading ? t('sendingBtn') : t('sendBtn')}
          </button>
        </form>
      )}

      {/* ── Footer ── */}
      <p className="mt-6 text-center text-theme-sm text-gray-500 dark:text-gray-400">
        {t('rememberPassword')}{' '}
        <Link
          href={`/${locale}/signin`}
          className="font-semibold text-brand-500 hover:text-brand-600 dark:text-brand-400 dark:hover:text-brand-300 transition-colors"
        >
          {t('signInLink')}
        </Link>
      </p>
    </div>
  );
};

export default ForgotPasswordForm;