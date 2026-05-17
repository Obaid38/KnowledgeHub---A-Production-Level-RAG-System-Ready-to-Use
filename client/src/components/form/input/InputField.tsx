'use client';

import { useState, forwardRef } from 'react';
import { Eye, EyeOff } from 'lucide-react';
import { cn } from '@/utils/index';

interface InputFieldProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label: string;
  error?: string;
  showPasswordToggle?: boolean;
  optional?: boolean;
  hint?: string;
}

const InputField = forwardRef<HTMLInputElement, InputFieldProps>(
  (
    {
      label,
      error,
      optional = false,
      showPasswordToggle = false,
      type = 'text',
      className,
      hint,
      ...inputProps
    },
    ref
  ) => {
    const [showPassword, setShowPassword] = useState(false);

    const inputType =
      showPasswordToggle && type === 'password'
        ? showPassword ? 'text' : 'password'
        : type;

    return (
      <div className="flex flex-col w-full">

        {/* ── Label ── */}
        <label className={cn(
          'text-theme-sm mb-1.5 font-medium transition-colors',
          error
            ? 'text-error-500 dark:text-error-400'
            : 'text-gray-700 dark:text-gray-400'
        )}>
          {label}{' '}
          {optional && (
            <span className={cn(
              'font-normal',
              error
                ? 'text-error-400 dark:text-error-300'
                : 'text-gray-400 dark:text-gray-500'
            )}>
              (optional)
            </span>
          )}
        </label>

        {/* ── Input ── */}
        <div className="relative">
          <input
            ref={ref}
            type={inputType}
            className={cn(
              // Base
              'h-11 w-full rounded-lg border appearance-none px-4 py-2.5 text-sm',
              'shadow-theme-xs focus:outline-none focus:ring-3',
              'placeholder:text-gray-400',
              // ── KEY FIX: explicit bg for both modes, no bg-transparent ──
              // Light: white  |  Dark: gray-900 (#101828)
              'bg-white dark:bg-gray-900',
              // Text
              'text-gray-800 dark:text-white/90',
              // Dark placeholder
              'dark:placeholder:text-white/30',
              // Password toggle padding
              showPasswordToggle && type === 'password' ? 'pr-10' : '',
              // Disabled
              inputProps.disabled && cn(
                'cursor-not-allowed opacity-50',
                'bg-gray-50 dark:bg-gray-800',
                'border-gray-300 dark:border-gray-700',
                'text-gray-500 dark:text-gray-400',
              ),
              // Error
              error && !inputProps.disabled && cn(
                'border-error-500 dark:border-error-500',
                'text-error-800 dark:text-error-400',
                'focus:ring-error-500/10 focus:border-error-500',
              ),
              // Normal
              !error && !inputProps.disabled && cn(
                'border-gray-300 dark:border-gray-700',
                'focus:border-brand-300 dark:focus:border-brand-800',
                'focus:ring-brand-500/10',
              ),
              className,
            )}
            {...inputProps}
          />

          {/* Password toggle */}
          {showPasswordToggle && type === 'password' && (
            <button
              type="button"
              onClick={() => setShowPassword((prev) => !prev)}
              className={cn(
                'absolute right-3 top-1/2 -translate-y-1/2 p-1',
                'flex items-center justify-center transition-colors',
                error
                  ? 'text-error-500 hover:text-error-600 dark:text-error-400 dark:hover:text-error-300'
                  : 'text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300',
              )}
              tabIndex={-1}
              aria-label="Toggle password visibility"
            >
              {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
            </button>
          )}
        </div>

        {/* Error */}
        {error && (
          <p className="mt-1.5 text-xs text-error-500 dark:text-error-400">{error}</p>
        )}

        {/* Hint */}
        {hint && !error && (
          <p className="mt-1.5 text-xs text-gray-500 dark:text-gray-400">{hint}</p>
        )}
      </div>
    );
  }
);

InputField.displayName = 'InputField';
export default InputField;