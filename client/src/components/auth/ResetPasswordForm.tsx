'use client';

import { useState, useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import { useRouter, useSearchParams } from 'next/navigation';
import { useLocale, useTranslations } from 'next-intl';
import Link from 'next/link';
import { ChevronLeft } from 'lucide-react';
import InputField from '../form/input/InputField';
import Logo from '../common/Logo';
import { useAuthStore } from '@/store/authStore';

const resetPasswordSchema = z
  .object({
    password: z
      .string()
      .min(6, 'Password must be at least 6 characters')
      .nonempty('Password is required'),
    confirmPassword: z.string().nonempty('Please confirm your password'),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: 'Passwords do not match',
    path: ['confirmPassword'],
  });

type ResetPasswordFormData = z.infer<typeof resetPasswordSchema>;

const ResetPasswordForm: React.FC = () => {
  const router = useRouter();
  const locale = useLocale();
  const t = useTranslations('auth.resetPassword');
  const searchParams = useSearchParams();
  const resetPassword = useAuthStore((s) => s.resetPassword);
  const [isLoading, setIsLoading] = useState(false);
  const [formError, setFormError] = useState('');
  const [successMessage, setSuccessMessage] = useState('');
  const [isTokenValid, setIsTokenValid] = useState(true);

  const token = searchParams.get('token');

  useEffect(() => {
    if (!token) {
      setIsTokenValid(false);
      setFormError(t('invalidToken'));
    }
  }, [token, t]);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ResetPasswordFormData>({
    resolver: zodResolver(resetPasswordSchema),
  });

  const onSubmit = async (values: ResetPasswordFormData) => {
    setFormError('');
    setSuccessMessage('');
    setIsLoading(true);
    try {
      if (!token) { setFormError(t('invalidToken')); return; }
      await resetPassword({ token, password: values.password });
      setSuccessMessage(t('successMessage'));
      setTimeout(() => { router.push(`/${locale}/signin`); }, 2000);
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : 'Failed to reset password. Please try again.';
      setFormError(errorMessage);
    } finally {
      setIsLoading(false);
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
      {isTokenValid && !successMessage && (
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
          <InputField
            label={t('newPasswordLabel')}
            type="password"
            placeholder={t('newPasswordPlaceholder')}
            showPasswordToggle
            {...register('password')}
            error={errors.password?.message}
            disabled={isLoading}
          />

          <InputField
            label={t('confirmPasswordLabel')}
            type="password"
            placeholder={t('confirmPasswordPlaceholder')}
            showPasswordToggle
            {...register('confirmPassword')}
            error={errors.confirmPassword?.message}
            disabled={isLoading}
          />

          <button
            type="submit"
            disabled={isLoading}
            className="btn-primary"
          >
            {isLoading ? t('resettingBtn') : t('resetBtn')}
          </button>
        </form>
      )}

      {/* ── Invalid / expired token ── */}
      {!isTokenValid && (
        <div className="text-center space-y-4">
          <p className="text-theme-sm text-gray-500 dark:text-gray-400">{t('expiredToken')}</p>
          <Link
            href={`/${locale}/forgot-password`}
            className="btn-primary block text-center"
          >
            {t('requestNewLink')}
          </Link>
        </div>
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

export default ResetPasswordForm;