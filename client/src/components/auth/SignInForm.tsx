'use client';

import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import { useRouter } from 'next/navigation';
import { useLocale, useTranslations } from 'next-intl';
import Link from 'next/link';
import InputField from '../form/input/InputField';
import { useAuthStore } from '@/store/authStore';
import Logo from '../common/Logo';

const signInSchema = z.object({
  email:    z.string().email('Invalid email').min(1, 'Email is required'),
  password: z.string().min(6, 'Password must be at least 6 characters'),
});

type SignInFormData = z.infer<typeof signInSchema>;

const SignInForm: React.FC = () => {
  const router  = useRouter();
  const locale  = useLocale();
  const t       = useTranslations('auth.signIn');
  const { login, isLoading, error, clearError } = useAuthStore();

  const [formError, setFormError] = useState('');

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<SignInFormData>({
    resolver: zodResolver(signInSchema),
  });

  const onSubmit = async (values: SignInFormData) => {
    setFormError('');
    clearError();
    try {
      const result = await login(values);
      if (result.status === 'mfa_required') {
        router.push(`/${locale}/mfa`);
        return;
      }
      // Admins → dashboard, regular users → Q&A
      const { user } = useAuthStore.getState();
      const isAdmin = user?.role === 'Admin' || user?.role === 'SuperAdmin';
      router.push(isAdmin ? `/${locale}` : `/${locale}/qa`);
    } catch (err) {
      setFormError(
        err instanceof Error ? err.message : 'Login failed. Please try again.'
      );
    }
  };

  return (
    <div className="auth-card">
      <Logo />

      <div className="text-center mb-7">
        <h1 className="mb-2">{t('title')}</h1>
        <p>{t('subtitle')}</p>
      </div>

      {(formError || error) && (
        <p className="server-error">{formError || error}</p>
      )}

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-5" noValidate>
        <InputField
          label={t('emailLabel')}
          type="email"
          placeholder={t('emailPlaceholder')}
          error={errors.email?.message}
          disabled={isLoading}
          {...register('email')}
        />

        <InputField
          label={t('passwordLabel')}
          type="password"
          placeholder={t('passwordPlaceholder')}
          showPasswordToggle
          error={errors.password?.message}
          disabled={isLoading}
          {...register('password')}
        />

        <div className="flex items-center justify-between gap-3">
          <Link
            href={`/${locale}/forgot-password`}
            className="text-theme-sm font-medium text-brand-500 hover:text-brand-600 dark:text-brand-400 dark:hover:text-brand-300 hover:underline transition-colors shrink-0"
          >
            {t('forgotPassword')}
          </Link>
        </div>

        <button
          type="submit"
          disabled={isLoading}
          className="btn-primary disabled:opacity-60"
        >
          {isLoading ? '…' : t('signInBtn')}
        </button>
      </form>

      <p className="text-center mt-6">
        {t('noAccount')}{' '}
        <Link
          href={`/${locale}/signup`}
          className="font-semibold text-brand-500 hover:text-brand-600 dark:text-brand-400 dark:hover:text-brand-300 underline hover:no-underline transition-colors"
        >
          {t('signUpLink')}
        </Link>
      </p>
    </div>
  );
};

export default SignInForm;
