"use client";

import React, { useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Mail, Lock, Eye, EyeOff, AlertCircle, ArrowRight, Loader2 } from 'lucide-react';
import { GoogleIcon } from './GoogleIcon';
import { AuthScreen, UserProfile } from '../types';
import { signIn } from '../api/auth-api';
import { saveSession } from '../lib/session';

interface SignInFormProps {
  onNavigate: (screen: AuthScreen) => void;
  onSuccess: (user: UserProfile) => void;
}

export const SignInForm: React.FC<SignInFormProps> = ({ onNavigate, onSuccess }) => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(true);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    // Validation
    if (!email.trim()) {
      setErrorMessage('Please enter your email address.');
      return;
    }

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email.trim())) {
      setErrorMessage('Please enter a valid email address.');
      return;
    }

    if (!password) {
      setErrorMessage('Please enter your password.');
      return;
    }

    if (password.length < 6) {
      setErrorMessage('Password must be at least 6 characters.');
      return;
    }

    setIsLoading(true);

    try {
      const session = await signIn(email, password, rememberMe);
      saveSession(session, rememberMe);
      onSuccess({
        name: session.user.display_name,
        email: session.user.email,
        preferredLanguage: session.user.preferred_language,
      });
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Unable to sign in. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleGoogleSignIn = () => {
    setErrorMessage('Google sign-in is not configured for this server yet.');
  };

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
        <h2 className="text-2xl font-bold text-slate-900 tracking-tight">Welcome back</h2>
        <p className="text-sm text-slate-500 mt-1">Sign in to continue to LinguaChat.</p>
      </div>

      {/* Error Alert */}
      <AnimatePresence>
        {errorMessage && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="mb-4 overflow-hidden"
          >
            <div className="flex items-center gap-2.5 p-3 rounded-xl bg-rose-50 border border-rose-200/80 text-rose-700 text-xs font-medium">
              <AlertCircle className="w-4 h-4 shrink-0 text-rose-600" />
              <span>{errorMessage}</span>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Continue with Google */}
      <button
        id="google-signin-button"
        type="button"
        onClick={handleGoogleSignIn}
        disabled={isLoading}
        className="w-full h-11 px-4 rounded-xl border border-slate-200 bg-white hover:bg-slate-50 hover:border-slate-300 text-slate-700 text-sm font-semibold transition-all flex items-center justify-center gap-3 shadow-2xs active:scale-[0.99] disabled:opacity-60 cursor-pointer"
      >
        <GoogleIcon className="w-4.5 h-4.5" />
        <span>Continue with Google</span>
      </button>

      {/* Divider */}
      <div className="relative my-5">
        <div className="absolute inset-0 flex items-center">
          <div className="w-full border-t border-slate-200" />
        </div>
        <div className="relative flex justify-center text-xs">
          <span className="bg-white px-3 text-slate-400 font-medium">or continue with email</span>
        </div>
      </div>

      {/* Form Fields */}
      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Email Field */}
        <div>
          <label htmlFor="signin-email" className="block text-xs font-semibold text-slate-700 mb-1.5">
            Email address
          </label>
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
              <Mail className="w-4 h-4" />
            </div>
            <input
              id="signin-email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => {
                setEmail(e.target.value);
                if (errorMessage) setErrorMessage(null);
              }}
              placeholder="you@example.com"
              className="w-full h-11 pl-10 pr-3.5 text-sm bg-slate-50/50 hover:bg-slate-50 focus:bg-white border border-slate-200 focus:border-indigo-500 rounded-xl outline-none focus:ring-3 focus:ring-indigo-500/15 transition-all text-slate-900 placeholder:text-slate-400"
            />
          </div>
        </div>

        {/* Password Field */}
        <div>
          <div className="flex items-center justify-between mb-1.5">
            <label htmlFor="signin-password" className="block text-xs font-semibold text-slate-700">
              Password
            </label>
          </div>
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
              <Lock className="w-4 h-4" />
            </div>
            <input
              id="signin-password"
              type={showPassword ? 'text' : 'password'}
              autoComplete="current-password"
              value={password}
              onChange={(e) => {
                setPassword(e.target.value);
                if (errorMessage) setErrorMessage(null);
              }}
              placeholder="Enter your password"
              className="w-full h-11 pl-10 pr-10 text-sm bg-slate-50/50 hover:bg-slate-50 focus:bg-white border border-slate-200 focus:border-indigo-500 rounded-xl outline-none focus:ring-3 focus:ring-indigo-500/15 transition-all text-slate-900 placeholder:text-slate-400"
            />
            <button
              id="toggle-password-visibility-button"
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              className="absolute inset-y-0 right-0 pr-3.5 flex items-center text-slate-400 hover:text-slate-600 transition-colors"
              aria-label={showPassword ? 'Hide password' : 'Show password'}
            >
              {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </button>
          </div>
        </div>

        {/* Options: Remember me & Forgot password */}
        <div className="flex items-center justify-between pt-0.5">
          <label className="flex items-center gap-2 cursor-pointer select-none">
            <input
              id="remember-me-checkbox"
              type="checkbox"
              checked={rememberMe}
              onChange={(e) => setRememberMe(e.target.checked)}
              className="w-4 h-4 rounded text-indigo-600 border-slate-300 focus:ring-indigo-500 focus:ring-offset-0 transition-colors accent-indigo-600"
            />
            <span className="text-xs text-slate-600 font-medium">Remember me</span>
          </label>
          <button
            id="forgot-password-link"
            type="button"
            onClick={() => onNavigate('forgot-password')}
            className="text-xs font-semibold text-indigo-600 hover:text-indigo-700 transition-colors hover:underline"
          >
            Forgot password?
          </button>
        </div>

        {/* Primary Submit Button */}
        <button
          id="signin-submit-button"
          type="submit"
          disabled={isLoading}
          className="w-full h-11 mt-2 px-4 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold transition-all shadow-sm shadow-indigo-600/25 active:scale-[0.99] flex items-center justify-center gap-2 disabled:opacity-70 cursor-pointer"
        >
          {isLoading ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>Signing in...</span>
            </>
          ) : (
            <>
              <span>Sign In</span>
              <ArrowRight className="w-4 h-4" />
            </>
          )}
        </button>
      </form>

      {/* Bottom Switcher */}
      <div className="mt-6 text-center text-xs text-slate-500">
        Don't have an account?{' '}
        <button
          id="navigate-signup-button"
          type="button"
          onClick={() => onNavigate('signup')}
          className="font-semibold text-indigo-600 hover:text-indigo-700 transition-colors hover:underline ml-1"
        >
          Sign up
        </button>
      </div>
    </motion.div>
  );
};
