import React, { useState } from 'react';
import { BarChart3, BookOpen, Check, Globe, Languages, Lightbulb, LogOut, Moon, Settings, Sun, User as UserIcon, X } from 'lucide-react';
import { AdminTab } from '../types';

interface SidebarProps {
  currentTab: AdminTab;
  onTabChange: (tab: AdminTab) => void;
  pendingSuggestionsCount: number;
  totalTermsCount: number;
  isMobileOpen?: boolean;
  onCloseMobile?: () => void;
  interfaceLanguage: 'vi' | 'en';
  theme: 'light' | 'dark';
  onInterfaceLanguageChange: (language: 'vi' | 'en') => void;
  onThemeChange: (theme: 'light' | 'dark') => void;
  adminName: string;
  adminEmail: string;
  adminRole: string;
}

type SettingsSection = 'language' | 'profile' | 'appearance';

export const Sidebar: React.FC<SidebarProps> = ({ currentTab, onTabChange, pendingSuggestionsCount, totalTermsCount, interfaceLanguage, theme, onInterfaceLanguageChange, onThemeChange, adminName, adminEmail, adminRole }) => {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [activeSection, setActiveSection] = useState<SettingsSection>('language');
  const isVietnamese = interfaceLanguage === 'vi';
  const initials = adminName.split(/\s+/).filter(Boolean).slice(-2).map((part) => part[0]).join('').toUpperCase() || 'AD';
  const navItems = [
    { id: 'analytics' as AdminTab, label: isVietnamese ? 'Thống kê' : 'Analytics', icon: BarChart3, badge: null },
    { id: 'glossary' as AdminTab, label: isVietnamese ? 'Thuật ngữ' : 'Glossary', icon: BookOpen, badge: totalTermsCount || null },
    { id: 'suggestions' as AdminTab, label: isVietnamese ? 'Đề xuất' : 'Suggestions', icon: Lightbulb, badge: pendingSuggestionsCount || null },
  ];
  const sections = [
    { id: 'language' as SettingsSection, label: isVietnamese ? 'Ngôn ngữ hiển thị' : 'Display language', icon: Languages },
    { id: 'profile' as SettingsSection, label: isVietnamese ? 'Hồ sơ' : 'Profile', icon: UserIcon },
    { id: 'appearance' as SettingsSection, label: isVietnamese ? 'Giao diện' : 'Appearance', icon: Moon },
  ];
  const openSettings = (section: SettingsSection = 'language') => { setActiveSection(section); setProfileOpen(false); setSettingsOpen(true); };
  const handleLogout = () => {
    ['access_token', 'refresh_token'].forEach((key) => { window.localStorage.removeItem(key); window.sessionStorage.removeItem(key); });
    window.location.replace('/login');
  };

  return (
    <aside id="admin-navigation-sidebar" className="fixed inset-y-0 left-0 z-50 flex w-[72px] min-w-[72px] flex-col items-center justify-between border-r border-[#E8EAF0] bg-white py-4 transition-colors dark:border-[#232630] dark:bg-[#1C1F27]" aria-label="Điều hướng quản trị">
      <div className="flex w-full flex-col items-center gap-5">
        <button id="admin-brand-logo-btn" type="button" aria-label="LinguaFlow" onClick={() => onTabChange('analytics')} className="group relative flex h-11 w-11 items-center justify-center rounded-2xl bg-gradient-to-tr from-[#2563EB] to-[#60A5FA] text-white shadow-md shadow-blue-600/25 transition-transform hover:scale-105 active:scale-95">
          <svg className="h-6 w-6 fill-current" viewBox="0 0 24 24" aria-hidden="true"><path d="M20 2H4C2.9 2 2 2.9 2 4V22L6 18H20C21.1 18 22 17.1 22 16V4C22 2.9 21.1 2 20 2Z" /><path d="M7 9H17M7 13H13" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" /></svg>
          <span className="absolute -right-1 -top-1 h-2.5 w-2.5 rounded-full border-2 border-blue-600 bg-amber-400" />
          <span className="pointer-events-none absolute left-[58px] z-50 whitespace-nowrap rounded-lg bg-gray-900 px-2.5 py-1 text-xs font-semibold text-white opacity-0 shadow-lg transition-opacity group-hover:opacity-100">LinguaFlow</span>
        </button>
        <div className="h-px w-8 bg-[#E8EAF0] dark:bg-[#2A2E3D]" />
        <nav className="flex w-full flex-col items-center gap-2 px-2" aria-label="Chức năng quản trị">
          {navItems.map((item) => { const Icon = item.icon; const active = currentTab === item.id; return (
            <div key={item.id} className="group relative flex w-full justify-center">
              <button type="button" id={`nav-item-${item.id}`} onClick={() => onTabChange(item.id)} aria-label={item.label} aria-current={active ? 'page' : undefined} className={`relative flex h-11 w-11 items-center justify-center rounded-xl transition-all ${active ? 'bg-[#EFF6FF] text-[#2563EB] shadow-sm dark:bg-[#2563EB]/20' : 'text-[#74798C] hover:bg-[#F7F8FC] hover:text-[#1E2230] dark:text-[#9DA3B4] dark:hover:bg-[#232630] dark:hover:text-white'}`}>
                <Icon className="h-5 w-5" strokeWidth={active ? 2.25 : 1.75} />
                {active && <span className="absolute -left-2 bottom-2 top-2 w-1 rounded-r-full bg-[#2563EB]" />}
                {item.badge !== null && <span className="absolute -right-1 -top-1 flex h-[18px] min-w-[18px] items-center justify-center rounded-full bg-[#2563EB] px-1 text-[10px] font-bold text-white ring-2 ring-white dark:ring-[#1C1F27]">{item.badge}</span>}
              </button>
              <span className="pointer-events-none absolute left-[60px] top-1/2 z-50 -translate-y-1/2 whitespace-nowrap rounded-lg bg-[#1E2230] px-2.5 py-1 text-xs font-medium text-white opacity-0 shadow-lg transition-opacity group-hover:opacity-100">{item.label}</span>
            </div>
          ); })}
        </nav>
      </div>

      <div className="flex w-full flex-col items-center gap-3 px-2">
        <div className="group relative flex w-full justify-center">
          <button id="admin-sidebar-settings-btn" type="button" onClick={() => openSettings('language')} aria-label={isVietnamese ? 'Cài đặt' : 'Settings'} className="flex h-11 w-11 items-center justify-center rounded-xl text-[#74798C] transition-colors hover:bg-[#F7F8FC] hover:text-[#1E2230] dark:text-[#9DA3B4] dark:hover:bg-[#232630] dark:hover:text-white"><Settings className="h-5 w-5 transition-transform group-hover:rotate-45" /></button>
          <span className="pointer-events-none absolute left-[60px] top-1/2 z-50 -translate-y-1/2 whitespace-nowrap rounded-lg bg-[#1E2230] px-2.5 py-1 text-xs font-medium text-white opacity-0 shadow-lg transition-opacity group-hover:opacity-100">{isVietnamese ? 'Cài đặt' : 'Settings'}</span>
        </div>
        <div className="relative">
          <button id="admin-profile-avatar-btn" type="button" onClick={() => setProfileOpen((open) => !open)} aria-label={`${isVietnamese ? 'Hồ sơ' : 'Profile'}: ${adminName}`} className="relative flex h-10 w-10 items-center justify-center rounded-full bg-[#EFF6FF] text-xs font-bold text-[#2563EB] ring-2 ring-[#E8EAF0] transition-all hover:ring-[#2563EB] dark:bg-[#2563EB]/20 dark:ring-[#2A2E3D]">{initials}<span className="absolute bottom-0 right-0 h-2.5 w-2.5 rounded-full bg-emerald-500 ring-2 ring-white dark:ring-[#1C1F27]" /></button>
          {profileOpen && <>
            <button type="button" aria-label={isVietnamese ? 'Đóng menu hồ sơ' : 'Close profile menu'} className="fixed inset-0 z-[59] cursor-default" onClick={() => setProfileOpen(false)} />
            <div id="admin-user-profile-popover" className="fixed bottom-4 left-[84px] z-[60] w-72 rounded-2xl border border-[#E8EAF0] bg-white p-3 shadow-xl dark:border-[#2A2E3D] dark:bg-[#1C1F27]">
              <div className="mb-2 flex items-center gap-3 rounded-xl bg-[#F7F8FC] p-2.5 dark:bg-[#232630]/60">
                <div className="relative flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-[#DBEAFE] text-sm font-bold text-[#2563EB] ring-2 ring-white dark:bg-[#2563EB]/20 dark:ring-[#1C1F27]">{initials}<span className="absolute bottom-0 right-0 h-3 w-3 rounded-full bg-emerald-500 ring-2 ring-white dark:ring-[#1C1F27]" /></div>
                <div className="min-w-0 flex-1"><h4 className="truncate text-sm font-semibold text-[#1E2230] dark:text-[#F5F6FA]">{adminName}</h4><p className="truncate text-xs text-[#74798C] dark:text-[#9DA3B4]">{adminEmail}</p><span className="mt-1 inline-flex items-center gap-1 rounded-md bg-[#2563EB]/10 px-1.5 py-0.5 text-[10px] font-medium text-[#2563EB]"><Globe className="h-2.5 w-2.5" />{isVietnamese ? 'Tiếng Việt' : 'English'}</span></div>
              </div>
              <div className="space-y-0.5 text-xs text-[#1E2230] dark:text-[#E2E5F0]">
                <button type="button" onClick={() => openSettings('profile')} className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left transition-colors hover:bg-[#F7F8FC] dark:hover:bg-[#232630]"><UserIcon className="h-4 w-4 text-[#74798C]" />{isVietnamese ? 'Hồ sơ của tôi' : 'My profile'}</button>
                <button type="button" onClick={() => onThemeChange(theme === 'dark' ? 'light' : 'dark')} className="flex w-full items-center justify-between rounded-lg px-3 py-2 text-left transition-colors hover:bg-[#F7F8FC] dark:hover:bg-[#232630]"><span className="flex items-center gap-2.5">{theme === 'dark' ? <Sun className="h-4 w-4 text-amber-500" /> : <Moon className="h-4 w-4 text-[#74798C]" />}{isVietnamese ? 'Giao diện' : 'Appearance'}</span><span className="text-[11px] font-medium uppercase text-[#74798C]">{theme === 'dark' ? (isVietnamese ? 'Tối' : 'Dark') : (isVietnamese ? 'Sáng' : 'Light')}</span></button>
                <button type="button" onClick={() => openSettings('language')} className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left transition-colors hover:bg-[#F7F8FC] dark:hover:bg-[#232630]"><Settings className="h-4 w-4 text-[#74798C]" />{isVietnamese ? 'Ngôn ngữ & Cài đặt' : 'Language & Settings'}</button>
              </div>
              <div className="my-2 border-t border-[#E8EAF0] dark:border-[#2A2E3D]" />
              <button type="button" onClick={handleLogout} style={{ color: theme === 'dark' ? '#FB7185' : '#E11D48' }} className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left text-xs transition-colors hover:bg-rose-50 dark:hover:bg-rose-950/30"><LogOut className="h-4 w-4" />{isVietnamese ? 'Đăng xuất' : 'Log out'}</button>
            </div>
          </>}
        </div>
      </div>

      {settingsOpen && <div id="admin-settings-modal-backdrop" className="fixed inset-0 z-[80] flex items-center justify-center bg-black/50 p-4 backdrop-blur-xs" onMouseDown={(event) => { if (event.target === event.currentTarget) setSettingsOpen(false); }}>
        <div id="admin-settings-modal" role="dialog" aria-modal="true" aria-labelledby="admin-settings-title" className="flex h-[560px] w-full max-w-2xl overflow-hidden rounded-3xl border border-[#E8EAF0] bg-white shadow-2xl dark:border-[#2A2E3D] dark:bg-[#1C1F27]">
          <aside className="w-56 shrink-0 border-r border-[#E8EAF0] bg-[#F7F8FC] p-3 dark:border-[#2A2E3D] dark:bg-[#14161C]">
            <h3 id="admin-settings-title" className="mb-2 px-3 py-2 text-base font-bold text-[#1E2230] dark:text-[#F5F6FA]">{isVietnamese ? 'Cài đặt' : 'Settings'}</h3>
            <nav className="space-y-1">{sections.map((section) => { const Icon = section.icon; const active = activeSection === section.id; return <button key={section.id} type="button" onClick={() => setActiveSection(section.id)} style={{ backgroundColor: active ? (theme === 'dark' ? 'rgba(37, 99, 235, 0.2)' : '#EFF6FF') : 'transparent', color: active ? '#2563EB' : theme === 'dark' ? '#9DA3B4' : '#74798C' }} className="flex w-full items-center gap-2.5 rounded-xl px-3 py-2 text-left text-xs font-semibold transition-colors hover:bg-[#F4F5F8] dark:hover:bg-[#232630]"><Icon className="h-4 w-4" />{section.label}</button>; })}</nav>
          </aside>
          <main className="flex min-w-0 flex-1 flex-col bg-white dark:bg-[#1C1F27]">
            <div className="flex items-center justify-between border-b border-[#E8EAF0] px-6 py-4 dark:border-[#2A2E3D]"><h4 className="text-base font-bold text-[#1E2230] dark:text-[#F5F6FA]">{sections.find((section) => section.id === activeSection)?.label}</h4><button type="button" onClick={() => setSettingsOpen(false)} aria-label={isVietnamese ? 'Đóng' : 'Close'} className="rounded-xl p-1.5 text-[#74798C] hover:bg-[#F7F8FC] hover:text-[#1E2230] dark:hover:bg-[#232630] dark:hover:text-white"><X className="h-5 w-5" /></button></div>
            <div className="flex-1 overflow-y-auto p-6 text-sm">
              {activeSection === 'language' && <div className="space-y-5"><div className="space-y-1.5"><label className="text-xs font-bold text-[#1E2230] dark:text-[#F5F6FA]">{isVietnamese ? 'Ngôn ngữ hiển thị yêu thích' : 'Preferred display language'}</label><select id="admin-settings-language-select" value={interfaceLanguage} onChange={(event) => onInterfaceLanguageChange(event.target.value as 'vi' | 'en')} className="h-11 w-full rounded-xl border border-transparent bg-[#F4F5F8] px-3 text-sm text-[#1E2230] outline-none focus:border-[#2563EB]/40 dark:bg-[#232630] dark:text-[#F5F6FA]"><option value="vi">🇻🇳 Tiếng Việt</option><option value="en">🇺🇸 English</option></select><p className="pt-0.5 text-xs text-[#74798C] dark:text-[#9DA3B4]">{isVietnamese ? 'Các nhãn và nội dung quản trị sẽ hiển thị bằng ngôn ngữ bạn chọn.' : 'Admin labels and content use your selected language.'}</p></div><div className="flex items-center justify-between rounded-2xl border border-[#E8EAF0] bg-[#F7F8FC] p-3.5 dark:border-[#2A2E3D] dark:bg-[#232630]/60"><div><h5 className="text-xs font-semibold text-[#1E2230] dark:text-[#F5F6FA]">{isVietnamese ? 'Ngôn ngữ hiện tại' : 'Current language'}</h5><p className="text-xs text-[#74798C] dark:text-[#9DA3B4]">{isVietnamese ? 'Tiếng Việt' : 'English'}</p></div><Check className="h-5 w-5 text-[#2563EB]" /></div></div>}
              {activeSection === 'profile' && <div className="space-y-5"><div className="flex items-center gap-4"><div className="flex h-16 w-16 items-center justify-center rounded-full bg-[#DBEAFE] text-xl font-bold text-[#2563EB] ring-2 ring-[#2563EB] dark:bg-[#2563EB]/20">{initials}</div><div><h5 className="text-sm font-bold text-[#1E2230] dark:text-[#F5F6FA]">{adminName}</h5><p className="text-xs text-[#74798C]">{adminEmail}</p></div></div><div className="grid gap-3"><div className="rounded-xl bg-[#F4F5F8] px-4 py-3 dark:bg-[#232630]"><p className="text-[10px] font-bold uppercase tracking-wide text-[#8A8F9E]">{isVietnamese ? 'Vai trò' : 'Role'}</p><p className="mt-1 text-sm font-semibold capitalize text-[#1E2230] dark:text-[#F5F6FA]">{adminRole}</p></div><div className="rounded-xl bg-[#F4F5F8] px-4 py-3 dark:bg-[#232630]"><p className="text-[10px] font-bold uppercase tracking-wide text-[#8A8F9E]">Email</p><p className="mt-1 text-sm text-[#1E2230] dark:text-[#F5F6FA]">{adminEmail}</p></div></div></div>}
              {activeSection === 'appearance' && <div className="space-y-3"><p className="text-xs text-[#74798C] dark:text-[#9DA3B4]">{isVietnamese ? 'Chọn giao diện sáng hoặc tối cho toàn bộ khu vực quản trị.' : 'Choose light or dark appearance for the admin area.'}</p><div className="grid grid-cols-2 gap-3"><button type="button" onClick={() => onThemeChange('light')} className={`flex items-center justify-center gap-2 rounded-xl border px-4 py-3 text-sm font-semibold ${theme === 'light' ? 'border-[#2563EB] bg-[#EFF6FF] text-[#2563EB]' : 'border-[#E8EAF0] text-[#74798C]'}`}><Sun className="h-4 w-4" />{isVietnamese ? 'Sáng' : 'Light'}</button><button type="button" onClick={() => onThemeChange('dark')} className={`flex items-center justify-center gap-2 rounded-xl border px-4 py-3 text-sm font-semibold ${theme === 'dark' ? 'border-[#2563EB] bg-[#2563EB]/20 text-[#2563EB]' : 'border-[#E8EAF0] text-[#74798C] dark:border-[#2A2E3D]'}`}><Moon className="h-4 w-4" />{isVietnamese ? 'Tối' : 'Dark'}</button></div></div>}
            </div>
          </main>
        </div>
      </div>}
    </aside>
  );
};
