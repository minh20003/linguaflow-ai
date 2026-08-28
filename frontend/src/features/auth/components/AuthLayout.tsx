"use client";

import React from 'react';
import { motion } from 'motion/react';
import { MessageSquareText, Sparkles, Globe, ArrowRightLeft } from 'lucide-react';

interface AuthLayoutProps {
  children: React.ReactNode;
}

export const AuthLayout: React.FC<AuthLayoutProps> = ({ children }) => {
  return (
    <div id="auth-app-shell" className="min-h-screen w-full bg-slate-50 text-slate-900 flex flex-col md:flex-row antialiased selection:bg-indigo-500 selection:text-white">
      {/* LEFT COLUMN (Desktop only: >= 768px) */}
      <div className="hidden md:flex md:w-1/2 lg:w-[48%] xl:w-[45%] bg-gradient-to-br from-indigo-50/80 via-purple-50/40 to-slate-100/70 border-r border-slate-200/80 p-8 lg:p-12 xl:p-16 flex-col justify-between relative overflow-hidden">
        {/* Ambient subtle glow shapes */}
        <div className="absolute -top-24 -left-24 w-96 h-96 bg-indigo-200/40 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute -bottom-24 -right-24 w-96 h-96 bg-purple-200/30 rounded-full blur-3xl pointer-events-none" />

        {/* Brand header */}
        <div className="relative z-10">
          <div className="inline-flex items-center gap-2.5 px-3 py-1.5 rounded-xl bg-white/90 border border-slate-200/70 shadow-xs mb-8">
            <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center text-white shadow-sm shadow-indigo-600/20">
              <MessageSquareText className="w-4 h-4" />
            </div>
            <div className="flex items-center gap-1.5">
              <span className="font-bold tracking-tight text-lg text-slate-900">LinguaFlow</span>
            </div>
          </div>

          <div className="max-w-md">
            <h1 className="text-3xl lg:text-4xl font-extrabold text-slate-900 tracking-tight leading-tight mb-4">
              Chat beyond <br />
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-600 to-purple-600">
                language barriers.
              </span>
            </h1>
            <p className="text-slate-600 text-sm lg:text-base leading-relaxed">
              Connect with anyone around the world with instant, natural auto-translation directly in your chat stream.
            </p>
          </div>
        </div>

        {/* Visual Multilingual Messaging Illustration */}
        <div className="relative z-10 my-8 py-4">
          <div className="relative max-w-sm mx-auto space-y-4">
            {/* Bubble 1: Vietnamese */}
            <motion.div
              initial={false}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.1 }}
              className="flex items-start gap-3 bg-white p-3.5 rounded-2xl border border-slate-200/80 shadow-sm shadow-slate-200/60"
            >
              <div className="w-9 h-9 rounded-xl bg-amber-100 flex items-center justify-center text-sm font-semibold text-amber-800 shrink-0">
                🇻🇳
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-2 mb-0.5">
                  <span className="text-xs font-semibold text-slate-800">Minh Anh</span>
                  <span className="text-[10px] text-slate-400">10:42 AM</span>
                </div>
                <p className="text-sm font-medium text-slate-900">Xin chào 👋</p>
                <div className="mt-1.5 flex items-center gap-1.5 text-[11px] text-indigo-600 font-medium bg-indigo-50/80 px-2 py-0.5 rounded-md w-fit">
                  <Sparkles className="w-3 h-3" />
                  <span>Translated: "Hello there 👋"</span>
                </div>
              </div>
            </motion.div>

            {/* Bubble 2: English (Self / Reply) */}
            <motion.div
              initial={false}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.25 }}
              className="flex items-start gap-3 bg-indigo-500 text-white p-3.5 rounded-2xl shadow-sm shadow-indigo-400/20 ml-6"
            >
              <div className="w-9 h-9 rounded-xl bg-white/20 flex items-center justify-center text-sm font-semibold text-white shrink-0">
                🇺🇸
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-2 mb-0.5">
                  <span className="text-xs font-semibold text-indigo-100">Alex</span>
                  <span className="text-[10px] text-indigo-200">10:43 AM</span>
                </div>
                <p className="text-sm font-medium text-white">Hello! Great to connect with you.</p>
                <div className="mt-1.5 flex items-center gap-1.5 text-[11px] text-indigo-100 font-medium bg-white/15 px-2 py-0.5 rounded-md w-fit">
                  <ArrowRightLeft className="w-3 h-3" />
                  <span>Auto-translating for group</span>
                </div>
              </div>
            </motion.div>

            {/* Bubble 3: Japanese */}
            <motion.div
              initial={false}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.4 }}
              className="flex items-start gap-3 bg-white p-3.5 rounded-2xl border border-slate-200/80 shadow-sm shadow-slate-200/60"
            >
              <div className="w-9 h-9 rounded-xl bg-rose-100 flex items-center justify-center text-sm font-semibold text-rose-800 shrink-0">
                🇯🇵
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-2 mb-0.5">
                  <span className="text-xs font-semibold text-slate-800">Yuki Tanaka</span>
                  <span className="text-[10px] text-slate-400">10:44 AM</span>
                </div>
                <p className="text-sm font-medium text-slate-900">こんにちは！よろしくお願いします 👋</p>
                <div className="mt-1.5 flex items-center gap-1.5 text-[11px] text-indigo-600 font-medium bg-indigo-50/80 px-2 py-0.5 rounded-md w-fit">
                  <Sparkles className="w-3 h-3" />
                  <span>Translated: "Hello! Nice to meet you 👋"</span>
                </div>
              </div>
            </motion.div>
          </div>
        </div>

        {/* Footer info badge */}
        <div className="relative z-10 flex items-center gap-4 text-xs text-slate-500">
          <div className="flex items-center gap-1.5">
            <Globe className="w-4 h-4 text-indigo-600" />
            <span>Auto Language Detection</span>
          </div>
          <span className="text-slate-300">•</span>
          <span>Real-time AI Translation</span>
          <span className="text-slate-300">•</span>
          <span>Secure Messaging</span>
        </div>
      </div>

      {/* RIGHT COLUMN (Authentication View Container) */}
      <div className="flex-1 flex flex-col justify-center items-center p-5 sm:p-8 md:p-10 lg:p-12 min-h-screen relative overflow-y-auto">
        {/* Mobile Header (< 768px) */}
        <div className="md:hidden w-full max-w-[420px] mb-6 pt-4 flex items-center justify-between">
          <div className="inline-flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center text-white shadow-xs">
              <MessageSquareText className="w-4 h-4" />
            </div>
            <span className="font-bold tracking-tight text-lg text-slate-900">LinguaFlow</span>
          </div>
          <span className="text-xs font-medium text-indigo-700 bg-indigo-50 border border-indigo-100 px-2.5 py-1 rounded-full">
            Multilingual
          </span>
        </div>

        {/* Central form wrapper (centered vertically, max width around 400-440px) */}
        <div className="w-full max-w-[420px] my-auto">
          {children}
        </div>

        {/* Mobile footer hint */}
        <div className="md:hidden w-full max-w-[420px] mt-6 pb-4 text-center text-xs text-slate-400">
          LinguaFlow • Multilingual Messaging Platform
        </div>
      </div>
    </div>
  );
};
