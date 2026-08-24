"use client";

import React, { useState } from 'react';
import { motion } from 'motion/react';
import { Check, ArrowRight, Languages, Sparkles } from 'lucide-react';
import { SUPPORTED_LANGUAGES } from '../constants/languages';
import { LanguageOption } from '../types';

interface LanguageOnboardingProps {
  initialLanguage?: string;
  onSelectLanguage: (languageId: string) => void;
  onContinue: () => void;
}

export const LanguageOnboarding: React.FC<LanguageOnboardingProps> = ({
  initialLanguage = 'vietnamese',
  onSelectLanguage,
  onContinue,
}) => {
  const [selectedLang, setSelectedLang] = useState<string>(initialLanguage);

  const handleSelect = (lang: LanguageOption) => {
    setSelectedLang(lang.id);
    onSelectLanguage(lang.id);
  };

  const currentSelectedObj = SUPPORTED_LANGUAGES.find((l) => l.id === selectedLang);

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      transition={{ duration: 0.25 }}
      className="bg-white rounded-2xl border border-slate-200/80 p-6 sm:p-8 shadow-sm shadow-slate-100"
    >
      {/* Title & Subtitle */}
      <div className="mb-5">
        <div className="w-10 h-10 rounded-xl bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600 mb-3 shadow-2xs">
          <Languages className="w-5 h-5" />
        </div>
        <h2 className="text-2xl font-bold text-slate-900 tracking-tight">
          What language do you prefer?
        </h2>
        <p className="text-xs sm:text-sm text-slate-500 mt-1 leading-relaxed">
          We'll automatically translate conversations into this language in real-time.
        </p>
      </div>

      {/* Language Selection Grid (10 languages) */}
      <div className="grid grid-cols-2 gap-2.5 max-h-[300px] sm:max-h-[340px] overflow-y-auto pr-1 py-1 custom-scrollbar">
        {SUPPORTED_LANGUAGES.map((lang) => {
          const isSelected = selectedLang === lang.id;
          return (
            <button
              id={`language-option-${lang.id}`}
              key={lang.id}
              type="button"
              onClick={() => handleSelect(lang)}
              className={`relative text-left p-3 rounded-xl border transition-all cursor-pointer flex flex-col justify-between ${
                isSelected
                  ? 'border-indigo-600 bg-indigo-50/70 shadow-xs ring-2 ring-indigo-500/20'
                  : 'border-slate-200 hover:border-slate-300 hover:bg-slate-50/70 bg-white'
              }`}
            >
              <div className="flex items-center justify-between w-full mb-1">
                <span className="text-xl" role="img" aria-label={lang.name}>
                  {lang.flag}
                </span>
                {isSelected && (
                  <div className="w-4.5 h-4.5 rounded-full bg-indigo-600 text-white flex items-center justify-center">
                    <Check className="w-3 h-3 stroke-[3]" />
                  </div>
                )}
              </div>
              <div>
                <p className={`text-xs sm:text-sm font-bold tracking-tight ${isSelected ? 'text-indigo-950' : 'text-slate-800'}`}>
                  {lang.nativeName}
                </p>
                <p className={`text-[11px] ${isSelected ? 'text-indigo-700 font-medium' : 'text-slate-400'}`}>
                  {lang.name}
                </p>
              </div>
            </button>
          );
        })}
      </div>

      {/* Real-time sample preview pill */}
      {currentSelectedObj && (
        <div className="mt-4 p-2.5 rounded-xl bg-slate-50 border border-slate-200/80 flex items-center justify-between text-xs">
          <div className="flex items-center gap-2 text-slate-600 truncate mr-2">
            <Sparkles className="w-3.5 h-3.5 text-indigo-600 shrink-0" />
            <span className="truncate">
              Greeting preview: <span className="font-semibold text-slate-900">{currentSelectedObj.sampleGreeting}</span>
            </span>
          </div>
          <span className="text-[10px] font-semibold uppercase tracking-wider text-indigo-700 bg-indigo-100/70 px-2 py-0.5 rounded-md shrink-0">
            {currentSelectedObj.code.toUpperCase()}
          </span>
        </div>
      )}

      {/* Primary Continue Button */}
      <button
        id="onboarding-continue-button"
        type="button"
        onClick={onContinue}
        className="w-full h-11 mt-5 px-4 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold transition-all shadow-sm shadow-indigo-600/25 active:scale-[0.99] flex items-center justify-center gap-2 cursor-pointer"
      >
        <span>Continue to LinguaFlow</span>
        <ArrowRight className="w-4 h-4" />
      </button>
    </motion.div>
  );
};
