'use client';

import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import { useRouter } from 'next/navigation';
import { useLocale, useTranslations } from 'next-intl';
import Link from 'next/link';
import Image from 'next/image';
import InputField from '../form/input/InputField';
import Button from '../ui/button/Button';
import { useAuthStore } from '@/store/authStore';
import Logo from '../common/Logo';

const SignUpForm: React.FC = () => {
  const router = useRouter();
  const locale = useLocale();
  const t = useTranslations('auth.signUp');
  const { signUp, isLoading, error, clearError } = useAuthStore();
  const [formError, setFormError] = useState('');

  const signUpSchema = z
    .object({
      firstName: z
        .string()
        .min(3, 'First name must be at least 3 characters')
        .nonempty('First name is required'),
      lastName: z
        .string()
        .min(3, 'Last name must be at least 3 characters')
        .nonempty('Last name is required'),
      email: z.string().email('Invalid email').nonempty('Email is required'),
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

  type SignUpFormData = z.infer<typeof signUpSchema>;

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<SignUpFormData>({
    resolver: zodResolver(signUpSchema),
  });

  const onSubmit = async (values: SignUpFormData) => {
    setFormError('');
    clearError();
    try {
      await signUp({
        firstName: values.firstName,
        lastName: values.lastName,
        email: values.email,
        password: values.password,
      });
      router.push(`/${locale}/signin`);
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : 'Registration failed. Please try again.';
      setFormError(errorMessage);
    }
  };

  return (
    <div className="auth-card">

      {/* ── Brand ── */}
     <Logo/>

      {/* ── Heading ── */}
      <div className="mb-6 text-center">
        <h2>{t('title')}</h2>
        <p className="mt-1">{t('subtitle')}</p>
      </div>

      {/* ── Server / form error ── */}
      {(formError || error) && (
        <div className="server-error">
          {formError || error}
        </div>
      )}

      {/* ── Form ── */}
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">

        {/* First name + Last name */}
        <div className="grid grid-cols-2 gap-4">
          <InputField
            label={t('firstNameLabel')}
            placeholder={t('firstNamePlaceholder')}
            {...register('firstName')}
            error={errors.firstName?.message}
            disabled={isLoading}
          />
          <InputField
            label={t('lastNameLabel')}
            placeholder={t('lastNamePlaceholder')}
            {...register('lastName')}
            error={errors.lastName?.message}
            disabled={isLoading}
          />
        </div>

        {/* Email */}
        <InputField
          label={t('emailLabel')}
          type="email"
          placeholder={t('emailPlaceholder')}
          {...register('email')}
          error={errors.email?.message}
          disabled={isLoading}
        />

        {/* Password */}
        <InputField
          label={t('passwordLabel')}
          type="password"
          placeholder={t('passwordPlaceholder')}
          showPasswordToggle
          {...register('password')}
          error={errors.password?.message}
          disabled={isLoading}
        />

        {/* Confirm password */}
        <InputField
          label="Confirm Password"
          type="password"
          placeholder="Re-enter your password"
          showPasswordToggle
          {...register('confirmPassword')}
          error={errors.confirmPassword?.message}
          disabled={isLoading}
        />

        {/* Submit */}
        <button
          type="submit"
          disabled={isLoading}
          className="btn-primary"
        >
          {isLoading ? '…' : t('signUpBtn')}
        </button>
      </form>

      {/* ── Footer ── */}
      <p className="mt-6 text-center text-theme-sm text-gray-500 dark:text-gray-400">
        {t('haveAccount')}{' '}
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

export default SignUpForm;