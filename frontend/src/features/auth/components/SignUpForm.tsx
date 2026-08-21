"use client";

import React, { useCallback, useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { User, Mail, Lock, Eye, EyeOff, AlertCircle, CheckCircle2, ArrowRight, Loader2 } from 'lucide-react';
import { GoogleSignInButton } from './GoogleSignInButton';
import { AuthScreen, UserProfile } from '../types';
import { signUp, signInWithGoogle } from '../api/auth-api';
import { saveSession } from '@/shared/lib/session';

interface SignUpFormProps {
  onNavigate: (screen: AuthScreen) => void;
  onSuccess: (user: Partial<UserProfile>) => void;
}

export const SignUpForm: React.FC<SignUpFormProps> = ({ onNavigate, onSuccess }) => {
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  // Field touched states for responsive inline validation
  const [touched, setTouched] = useState({
    fullName: false,
    email: false,
    password: false,
    confirmPassword: false,
  });

  const [formError, setFormError] = useState<string | null>(null);

  // Validation logic
  const isEmailValid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());
  const isPasswordLengthOk = password.length >= 8;
  const hasLetterAndNumber = /[a-zA-Z]/.test(password) && /[0-9]/.test(password);
  const isPasswordStrong = isPasswordLengthOk && hasLetterAndNumber;
  const isPasswordMatch = confirmPassword.length > 0 && password === confirmPassword;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setTouched({
      fullName: true,
      email: true,
      password: true,
      confirmPassword: true,
    });

    if (!fullName.trim()) {
      setFormError('Please enter your full name.');
      return;
    }

    if (!isEmailValid) {
      setFormError('Please enter a valid email address.');
      return;
    }

    if (!isPasswordStrong) {
      setFormError('Password must be at least 8 characters and include both letters and numbers.');
      return;
    }

    if (password !== confirmPassword) {
      setFormError('Passwords do not match.');
      return;
    }

    setFormError(null);
    setIsLoading(true);

    try {
      const session = await signUp({
        fullName,
        email,
        password,
        preferredLanguage: 'vi',
      });
      saveSession(session, true);
      onSuccess({
        name: session.user.display_name,
        email: session.user.email,
        preferredLanguage: session.user.preferred_language,
      });
      onNavigate('language-onboarding');
    } catch (error) {
      setFormError(error instanceof Error ? error.message : 'Unable to create your account. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleGoogleSignUp = useCallback(async (credential: string) => {
    setFormError(null);
    setIsLoading(true);
    try {
      const session = await signInWithGoogle(credential);
      saveSession(session, true);
      onSuccess({ name: session.user.display_name, email: session.user.email, preferredLanguage: session.user.preferred_language });
      onNavigate('language-onboarding');
    } catch (error) {
      setFormError(error instanceof Error ? error.message : 'Unable to sign in with Google.');
    } finally {
      setIsLoading(false);
    }
  }, [onNavigate, onSuccess]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      transition={{ duration: 0.25 }}
      className="bg-white rounded-2xl border border-slate-200/80 p-6 sm:p-8 shadow-sm shadow-slate-100"
    >
      {/* Title & Subtitle */}
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-slate-900 tracking-tight">Create your account</h2>
        <p className="text-sm text-slate-500 mt-1">Chat across 10+ languages with automatic translation.</p>
      </div>

      {/* Error Alert */}
      <AnimatePresence>
        {formError && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="mb-4 overflow-hidden"
          >
            <div className="flex items-center gap-2.5 p-3 rounded-xl bg-rose-50 border border-rose-200/80 text-rose-700 text-xs font-medium">
              <AlertCircle className="w-4 h-4 shrink-0 text-rose-600" />
              <span>{formError}</span>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Continue with Google */}
      <GoogleSignInButton
        disabled={isLoading}
        onCredential={handleGoogleSignUp}
        onError={setFormError}
      />

      {/* Divider */}
      <div className="relative my-5">
        <div className="absolute inset-0 flex items-center">
          <div className="w-full border-t border-slate-200" />
        </div>
        <div className="relative flex justify-center text-xs">
          <span className="bg-white px-3 text-slate-400 font-medium">Or continue with email</span>
        </div>
      </div>

      {/* Form Fields */}
      <form onSubmit={handleSubmit} className="space-y-3.5">
        {/* Full Name */}
        <div>
          <label htmlFor="signup-name" className="block text-xs font-semibold text-slate-700 mb-1">
            Full name
          </label>
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
              <User className="w-4 h-4" />
            </div>
            <input
              id="signup-name"
              type="text"
              autoComplete="name"
              value={fullName}
              onChange={(e) => {
                setFullName(e.target.value);
                if (formError) setFormError(null);
              }}
              onBlur={() => setTouched({ ...touched, fullName: true })}
              placeholder="Your name"
              className="w-full h-11 pl-10 pr-3.5 text-sm bg-slate-50/50 hover:bg-slate-50 focus:bg-white border border-slate-200 focus:border-indigo-500 rounded-xl outline-none focus:ring-3 focus:ring-indigo-500/15 transition-all text-slate-900 placeholder:text-slate-400"
            />
          </div>
          {touched.fullName && !fullName.trim() && (
            <p className="text-[11px] text-rose-500 mt-1">Full name is required</p>
          )}
        </div>

        {/* Email */}
        <div>
          <label htmlFor="signup-email" className="block text-xs font-semibold text-slate-700 mb-1">
            Email address
          </label>
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
              <Mail className="w-4 h-4" />
            </div>
            <input
              id="signup-email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => {
                setEmail(e.target.value);
                if (formError) setFormError(null);
              }}
              onBlur={() => setTouched({ ...touched, email: true })}
              placeholder="you@example.com"
              className={`w-full h-11 pl-10 pr-3.5 text-sm bg-slate-50/50 hover:bg-slate-50 focus:bg-white border rounded-xl outline-none transition-all text-slate-900 placeholder:text-slate-400 ${
                touched.email && !isEmailValid && email
                  ? 'border-rose-300 focus:border-rose-500 focus:ring-3 focus:ring-rose-500/15'
                  : 'border-slate-200 focus:border-indigo-500 focus:ring-3 focus:ring-indigo-500/15'
              }`}
            />
          </div>
          {touched.email && email.length > 0 && !isEmailValid && (
            <p className="text-[11px] text-rose-500 mt-1 flex items-center gap-1">
              <AlertCircle className="w-3 h-3" /> Please enter a valid email format
            </p>
          )}
        </div>

        {/* Password */}
        <div>
          <label htmlFor="signup-password" className="block text-xs font-semibold text-slate-700 mb-1">
            Password
          </label>
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
              <Lock className="w-4 h-4" />
            </div>
            <input
              id="signup-password"
              type={showPassword ? 'text' : 'password'}
              autoComplete="new-password"
              value={password}
              onChange={(e) => {
                setPassword(e.target.value);
                if (formError) setFormError(null);
              }}
              onBlur={() => setTouched({ ...touched, password: true })}
              placeholder="Enter your password"
              className="w-full h-11 pl-10 pr-10 text-sm bg-slate-50/50 hover:bg-slate-50 focus:bg-white border border-slate-200 focus:border-indigo-500 rounded-xl outline-none focus:ring-3 focus:ring-indigo-500/15 transition-all text-slate-900 placeholder:text-slate-400"
            />
            <button
              id="toggle-signup-password-visibility-button"
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              className="absolute inset-y-0 right-0 pr-3.5 flex items-center text-slate-400 hover:text-slate-600 transition-colors"
            >
              {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </button>
          </div>
          {/* Real-time inline password strength indicators */}
          {password.length > 0 && (
            <div className="mt-1.5 space-y-1">
              <div className="flex items-center gap-1.5 text-[11px]">
                {isPasswordLengthOk ? (
                  <span className="text-emerald-600 flex items-center gap-1 font-medium">
                    <CheckCircle2 className="w-3 h-3" /> At least 8 characters
                  </span>
                ) : (
                  <span className="text-slate-400 flex items-center gap-1">
                    • Minimum 8 characters ({password.length}/8)
                  </span>
                )}
              </div>
              <div className="flex items-center gap-1.5 text-[11px]">
                {hasLetterAndNumber ? (
                  <span className="text-emerald-600 flex items-center gap-1 font-medium">
                    <CheckCircle2 className="w-3 h-3" /> Contains letters & numbers
                  </span>
                ) : (
                  <span className="text-slate-400 flex items-center gap-1">
                    • Must include letters and numbers
                  </span>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Confirm Password */}
        <div>
          <label htmlFor="signup-confirm-password" className="block text-xs font-semibold text-slate-700 mb-1">
            Confirm password
          </label>
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
              <Lock className="w-4 h-4" />
            </div>
            <input
              id="signup-confirm-password"
              type={showConfirmPassword ? 'text' : 'password'}
              autoComplete="new-password"
              value={confirmPassword}
              onChange={(e) => {
                setConfirmPassword(e.target.value);
                if (formError) setFormError(null);
              }}
              onBlur={() => setTouched({ ...touched, confirmPassword: true })}
              placeholder="Re-enter your password"
              className={`w-full h-11 pl-10 pr-10 text-sm bg-slate-50/50 hover:bg-slate-50 focus:bg-white border rounded-xl outline-none transition-all text-slate-900 placeholder:text-slate-400 ${
                touched.confirmPassword && confirmPassword && !isPasswordMatch
                  ? 'border-rose-300 focus:border-rose-500 focus:ring-3 focus:ring-rose-500/15'
                  : 'border-slate-200 focus:border-indigo-500 focus:ring-3 focus:ring-indigo-500/15'
              }`}
            />
            <button
              id="toggle-signup-confirm-password-visibility-button"
              type="button"
              onClick={() => setShowConfirmPassword(!showConfirmPassword)}
              className="absolute inset-y-0 right-0 pr-3.5 flex items-center text-slate-400 hover:text-slate-600 transition-colors"
            >
              {showConfirmPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </button>
          </div>
          {touched.confirmPassword && confirmPassword.length > 0 && (
            <div className="mt-1">
              {isPasswordMatch ? (
                <span className="text-emerald-600 text-[11px] font-medium flex items-center gap-1">
                  <CheckCircle2 className="w-3 h-3" /> Passwords match
                </span>
              ) : (
                <span className="text-rose-500 text-[11px] font-medium flex items-center gap-1">
                  <AlertCircle className="w-3 h-3" /> Passwords do not match
                </span>
              )}
            </div>
          )}
        </div>

        {/* Primary Submit Button */}
        <button
          id="signup-submit-button"
          type="submit"
          disabled={isLoading}
          className="w-full h-11 mt-3 px-4 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold transition-all shadow-sm shadow-indigo-600/25 active:scale-[0.99] flex items-center justify-center gap-2 disabled:opacity-70 cursor-pointer"
        >
          {isLoading ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>Creating account...</span>
            </>
          ) : (
            <>
              <span>Create account</span>
              <ArrowRight className="w-4 h-4" />
            </>
          )}
        </button>
      </form>

      {/* Bottom Switcher */}
      <div className="mt-6 text-center text-xs text-slate-500">
        Already have an account?{' '}
        <button
          id="navigate-signin-button"
          type="button"
          onClick={() => onNavigate('signin')}
          className="font-semibold text-indigo-600 hover:text-indigo-700 transition-colors hover:underline ml-1"
        >
          Sign in
        </button>
      </div>
    </motion.div>
  );
};
