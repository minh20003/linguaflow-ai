import React, { useState } from 'react';
import { AppSettings, User, LanguageCode } from '../types';
import { CHAT_LANGUAGES } from '../constants';
import { settingText, t } from '../i18n';
import {
  X,
  Languages,
  User as UserIcon,

  Bell,
  Shield,
  Bot,
  Check,
  Globe2,
  Volume2,
  Eye
} from 'lucide-react';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  settings: AppSettings;
  onUpdateSettings: (newSettings: Partial<AppSettings>) => void;
  currentUser: User;
  onUpdateUser: (newUser: Partial<User>) => void;
}

type SettingsSection = 'language' | 'profile' | 'notifications' | 'privacy' | 'ai';

const copy = settingText;

export const SettingsModal: React.FC<SettingsModalProps> = ({
  isOpen,
  onClose,
  settings,
  onUpdateSettings,
  currentUser,
  onUpdateUser,
}) => {
  const language = settings.preferredLanguage;
  const [activeSection, setActiveSection] = useState<SettingsSection>('language');
  const [name, setName] = useState(currentUser.name);
  const [bio, setBio] = useState(currentUser.bio || '');

  if (!isOpen) return null;

  const sections = [
    { id: 'language' as SettingsSection, label: t(language, 'language'), icon: Languages },
    { id: 'profile' as SettingsSection, label: t(language, 'profile'), icon: UserIcon },

    { id: 'notifications' as SettingsSection, label: t(language, 'notifications'), icon: Bell },
    { id: 'privacy' as SettingsSection, label: t(language, 'privacy'), icon: Shield },
    { id: 'ai' as SettingsSection, label: t(language, 'aiTools'), icon: Bot },
  ];

  const handleSaveProfile = () => {
    onUpdateUser({ name, bio });
  };

  return (
    <div
      id="settings-modal-backdrop"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs animate-in fade-in duration-150"
    >
      <div
        id="settings-modal"
        className="w-full max-w-2xl h-[560px] bg-white dark:bg-[#1C1F27] rounded-3xl shadow-2xl border border-[#E8EAF0] dark:border-[#2A2E3D] overflow-hidden flex flex-col md:flex-row animate-in zoom-in-95 duration-150"
      >
        {/* Left Settings Navigation Rail */}
        <aside className="w-full md:w-56 bg-[#F7F8FC] dark:bg-[#14161C] border-r border-[#E8EAF0] dark:border-[#2A2E3D] p-3 flex md:flex-col justify-between flex-shrink-0">
          <div>
            <div className="flex items-center gap-2 px-3 py-2 mb-2">
              <h3 className="text-base font-bold text-[#1E2230] dark:text-[#F5F6FA]">
                {t(language, 'settings')}
              </h3>
            </div>

            <nav className="space-y-1">
              {sections.map((sec) => {
                const Icon = sec.icon;
                const isActive = activeSection === sec.id;
                return (
                  <button
                    key={sec.id}
                    onClick={() => setActiveSection(sec.id)}
                    className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-xl text-xs font-semibold transition-colors text-left ${
                      isActive
                        ? 'bg-[#EFF6FF] dark:bg-[#2563EB]/20 text-[#2563EB]'
                        : 'text-[#74798C] dark:text-[#9DA3B4] hover:bg-[#F4F5F8] dark:hover:bg-[#232630] hover:text-[#1E2230]'
                    }`}
                  >
                    <Icon className="w-4 h-4" />
                    <span>{sec.label}</span>
                  </button>
                );
              })}
            </nav>
          </div>
        </aside>

        {/* Right Content Area */}
        <main className="flex-1 flex flex-col h-full overflow-hidden bg-white dark:bg-[#1C1F27]">
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-[#E8EAF0] dark:border-[#2A2E3D]">
            <h4 className="text-base font-bold text-[#1E2230] dark:text-[#F5F6FA]">
              {sections.find((s) => s.id === activeSection)?.label}
            </h4>
            <button
              onClick={onClose}
              className="p-1.5 rounded-xl text-[#74798C] hover:text-[#1E2230] dark:hover:text-white hover:bg-[#F7F8FC] dark:hover:bg-[#232630]"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Body content */}
          <div className="flex-1 overflow-y-auto p-6 space-y-5 text-sm">
            {/* 1. Language & Translation Section */}
            {activeSection === 'language' && (
              <div className="space-y-5">
                {/* Preferred Language */}
                <div className="space-y-1.5">
                  <label className="text-xs font-bold text-[#1E2230] dark:text-[#F5F6FA]">
                    {copy(language, 'Preferred Language')}
                  </label>
                  <select
                    id="settings-language-select"
                    value={settings.preferredLanguage}
                    onChange={(e) =>
                      onUpdateSettings({ preferredLanguage: e.target.value as LanguageCode })
                    }
                    className="w-full h-11 px-3 bg-[#F4F5F8] dark:bg-[#232630] text-sm text-[#1E2230] dark:text-[#F5F6FA] rounded-xl border border-transparent focus:border-[#2563EB]/40 focus:outline-none"
                  >
                    {CHAT_LANGUAGES.map((lang) => (
                      <option key={lang.code} value={lang.code}>
                        {lang.flag} {lang.name} — {lang.nativeName}
                      </option>
                    ))}
                  </select>
                  <p className="text-xs text-[#74798C] dark:text-[#9DA3B4] pt-0.5">
                    {copy(language, 'Messages in other languages will automatically appear in your preferred language.')}
                  </p>
                </div>

                {/* Automatic Translation Toggle */}
                <div className="flex items-center justify-between p-3.5 rounded-2xl bg-[#F7F8FC] dark:bg-[#232630]/60 border border-[#E8EAF0] dark:border-[#2A2E3D]">
                  <div>
                    <h5 className="font-semibold text-xs text-[#1E2230] dark:text-[#F5F6FA]">
                      {copy(language, 'Automatic Translation')}
                    </h5>
                    <p className="text-xs text-[#74798C] dark:text-[#9DA3B4]">
                      {copy(language, 'Translate foreign incoming messages instantly')}
                    </p>
                  </div>
                  <button
                    onClick={() =>
                      onUpdateSettings({ autoTranslate: !settings.autoTranslate })
                    }
                    className={`relative w-11 h-6 rounded-full transition-colors ${
                      settings.autoTranslate ? 'bg-[#2563EB]' : 'bg-[#CED2DE] dark:bg-[#3A3F50]'
                    }`}
                  >
                    <span
                      className={`absolute top-1 left-1 w-4 h-4 rounded-full bg-white transition-transform ${
                        settings.autoTranslate ? 'translate-x-5' : ''
                      }`}
                    />
                  </button>
                </div>

                {/* Translation Tone */}
                <div className="space-y-1.5">
                  <label className="text-xs font-bold text-[#1E2230] dark:text-[#F5F6FA]">
                    {copy(language, 'Translation Tone')}
                  </label>
                  <div className="grid grid-cols-3 gap-2">
                    {(['natural', 'formal', 'friendly'] as const).map((tone) => (
                      <button
                        key={tone}
                        onClick={() => onUpdateSettings({ translationTone: tone })}
                        className={`p-2.5 rounded-xl border text-xs font-semibold capitalize transition-all ${
                          settings.translationTone === tone
                            ? 'border-[#2563EB] bg-[#EFF6FF] dark:bg-[#2563EB]/20 text-[#2563EB]'
                            : 'border-[#E8EAF0] dark:border-[#2A2E3D] text-[#74798C] hover:bg-[#F7F8FC]'
                        }`}
                      >
                        {copy(language, tone)}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* 2. Profile Section */}
            {activeSection === 'profile' && (
              <div className="space-y-4">
                <div className="flex items-center gap-4">
                  <img
                    src={currentUser.avatar}
                    alt={currentUser.name}
                    className="w-16 h-16 rounded-full object-cover ring-2 ring-[#2563EB]"
                    referrerPolicy="no-referrer"
                  />
                  <div>
                    <h5 className="font-bold text-sm text-[#1E2230] dark:text-[#F5F6FA]">
                      {currentUser.name}
                    </h5>
                    <p className="text-xs text-[#74798C]">{currentUser.email}</p>
                  </div>
                </div>

                <div className="space-y-1">
                  <label className="text-xs font-bold text-[#1E2230] dark:text-[#F5F6FA]">
                    {copy(language, 'Display Name')}
                  </label>
                  <input
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    className="w-full h-10 px-3 bg-[#F4F5F8] dark:bg-[#232630] text-xs text-[#1E2230] dark:text-[#F5F6FA] rounded-xl border border-transparent focus:border-[#2563EB]/40 focus:outline-none"
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-xs font-bold text-[#1E2230] dark:text-[#F5F6FA]">
                    {copy(language, 'Bio')}
                  </label>
                  <textarea
                    rows={2}
                    value={bio}
                    onChange={(e) => setBio(e.target.value)}
                    className="w-full p-2.5 bg-[#F4F5F8] dark:bg-[#232630] text-xs text-[#1E2230] dark:text-[#F5F6FA] rounded-xl border border-transparent focus:border-[#2563EB]/40 focus:outline-none resize-none"
                  />
                </div>

                <button
                  onClick={handleSaveProfile}
                  className="px-4 py-2 bg-[#2563EB] text-white text-xs font-semibold rounded-xl hover:bg-[#1D4ED8] shadow-sm transition-all"
                >
                  {copy(language, 'Save Profile Changes')}
                </button>
              </div>
            )}

            {/* 3. Notifications */}
            {activeSection === 'notifications' && (
              <div className="space-y-3">
                <div className="flex items-center justify-between p-3.5 rounded-2xl bg-[#F7F8FC] dark:bg-[#232630]/60 border border-[#E8EAF0] dark:border-[#2A2E3D]">
                  <div>
                    <h5 className="font-semibold text-xs text-[#1E2230] dark:text-[#F5F6FA]">
                      {copy(language, 'Sound Notifications')}
                    </h5>
                    <p className="text-xs text-[#74798C]">{copy(language, 'Play audio chime on incoming messages')}</p>
                  </div>
                  <button
                    onClick={() =>
                      onUpdateSettings({ soundEnabled: !settings.soundEnabled })
                    }
                    className={`relative w-11 h-6 rounded-full transition-colors ${
                      settings.soundEnabled ? 'bg-[#2563EB]' : 'bg-[#CED2DE] dark:bg-[#3A3F50]'
                    }`}
                  >
                    <span
                      className={`absolute top-1 left-1 w-4 h-4 rounded-full bg-white transition-transform ${
                        settings.soundEnabled ? 'translate-x-5' : ''
                      }`}
                    />
                  </button>
                </div>
              </div>
            )}

            {/* 4. Privacy */}
            {activeSection === 'privacy' && (
              <div className="space-y-3">
                <div className="flex items-center justify-between p-3.5 rounded-2xl bg-[#F7F8FC] dark:bg-[#232630]/60 border border-[#E8EAF0] dark:border-[#2A2E3D]">
                  <div>
                    <h5 className="font-semibold text-xs text-[#1E2230] dark:text-[#F5F6FA]">
                      {copy(language, 'Read Receipts')}
                    </h5>
                    <p className="text-xs text-[#74798C]">{copy(language, 'Let contacts see when you read their messages')}</p>
                  </div>
                  <button
                    onClick={() =>
                      onUpdateSettings({ readReceipts: !settings.readReceipts })
                    }
                    className={`relative w-11 h-6 rounded-full transition-colors ${
                      settings.readReceipts ? 'bg-[#2563EB]' : 'bg-[#CED2DE] dark:bg-[#3A3F50]'
                    }`}
                  >
                    <span
                      className={`absolute top-1 left-1 w-4 h-4 rounded-full bg-white transition-transform ${
                        settings.readReceipts ? 'translate-x-5' : ''
                      }`}
                    />
                  </button>
                </div>
              </div>
            )}

            {/* 6. Personal assistant chatbot */}
            {activeSection === 'ai' && (
              <div className="space-y-3">
                <div className="flex items-center gap-3 rounded-2xl bg-gradient-to-r from-[#EFF6FF] to-violet-50 p-4 dark:from-[#2563EB]/20 dark:to-violet-500/15">
                  <div className="flex h-12 w-12 flex-none items-center justify-center rounded-2xl bg-gradient-to-br from-[#2563EB] to-violet-600 text-white shadow-md shadow-[#2563EB]/20">
                    <Bot className="h-6 w-6" />
                  </div>
                  <div className="min-w-0">
                    <h5 className="text-sm font-bold text-[#1E2230] dark:text-[#F5F6FA]">
                      {copy(language, 'AI Smart Assistance')}
                    </h5>
                    <p className="mt-0.5 text-xs leading-relaxed text-[#74798C] dark:text-[#9DA3B4]">
                      {copy(language, 'Enable quick rewrites, tone polish & auto grammar')}
                    </p>
                  </div>
                </div>
                <div className="flex items-center justify-between p-3.5 rounded-2xl bg-[#F7F8FC] dark:bg-[#232630]/60 border border-[#E8EAF0] dark:border-[#2A2E3D]">
                  <div>
                    <h5 className="font-semibold text-xs text-[#1E2230] dark:text-[#F5F6FA]">
                      {copy(language, 'Enable personal assistant')}
                    </h5>
                    <p className="text-xs text-[#74798C]">{copy(language, 'Show the assistant in your conversations')}</p>
                  </div>
                  <button
                    onClick={() =>
                      onUpdateSettings({
                        aiSmartAssistance: !settings.aiSmartAssistance,
                      })
                    }
                    className={`relative w-11 h-6 rounded-full transition-colors ${
                      settings.aiSmartAssistance ? 'bg-[#2563EB]' : 'bg-[#CED2DE] dark:bg-[#3A3F50]'
                    }`}
                  >
                    <span
                      className={`absolute top-1 left-1 w-4 h-4 rounded-full bg-white transition-transform ${
                        settings.aiSmartAssistance ? 'translate-x-5' : ''
                      }`}
                    />
                  </button>
                </div>
              </div>
            )}
          </div>
        </main>
      </div>
    </div>
  );
};
