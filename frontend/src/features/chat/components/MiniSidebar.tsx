import React, { useState } from 'react';
import { SidebarTab, User, AppSettings } from '../types';
import {
  MessageSquare,
  BookUser,
  UsersRound,
  CalendarDays,
  Settings,
  Globe2
} from 'lucide-react';
import { UserProfileMenu } from './UserProfileMenu';
import { t, tx } from '../i18n';

interface MiniSidebarProps {
  activeTab: SidebarTab;
  onTabChange: (tab: SidebarTab) => void;
  currentUser: User;
  settings: AppSettings;
  onOpenSettings: () => void;
  onToggleTheme: () => void;
  onLogout: () => void;
  isLoggingOut?: boolean;
  unreadChatsCount: number;
}

export const MiniSidebar: React.FC<MiniSidebarProps> = ({
  activeTab,
  onTabChange,
  currentUser,
  settings,
  onOpenSettings,
  onToggleTheme,
  onLogout,
  isLoggingOut,
  unreadChatsCount,
}) => {
  const [profileOpen, setProfileOpen] = useState(false);
  const interfaceLanguage = settings.interfaceLanguage;

  const navItems = [
    {
      id: 'chats' as SidebarTab,
      label: t(interfaceLanguage, 'chats'),
      icon: MessageSquare,
      badge: unreadChatsCount > 0 ? unreadChatsCount : null,
    },
    {
      id: 'contacts' as SidebarTab,
      label: tx(interfaceLanguage, 'Contacts'),
      icon: BookUser,
    },
    {
      id: 'groups' as SidebarTab,
      label: t(interfaceLanguage, 'groups'),
      icon: UsersRound,
    },
    {
      id: 'calendar' as SidebarTab,
      label: 'Personal calendar',
      icon: CalendarDays,
    },
  ];

  return (
    <aside
      id="mini-navigation-sidebar"
      className="relative flex flex-col items-center justify-between w-[72px] min-w-[72px] h-screen bg-white dark:bg-[#1C1F27] border-r border-[#E8EAF0] dark:border-[#232630] py-4 select-none z-30 transition-colors"
      aria-label="Sidebar Navigation"
    >
      {/* Top Section: Brand Logo & Navigation */}
      <div className="flex flex-col items-center w-full gap-5">
        {/* LinguaFlow Logo Symbol */}
        <button
          id="sidebar-logo-button"
          onClick={() => onTabChange('chats')}
          aria-label="LinguaFlow Home"
          className="group relative flex items-center justify-center w-11 h-11 rounded-2xl bg-gradient-to-tr from-[#2563EB] to-[#60A5FA] text-white shadow-md shadow-[#2563EB]/25 hover:scale-105 active:scale-95 transition-all"
        >
          {/* Logo SVG: Speech bubble with global connection accent */}
          <div className="relative flex items-center justify-center">
            <svg
              className="w-6 h-6 fill-current"
              viewBox="0 0 24 24"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                d="M20 2H4C2.9 2 2 2.9 2 4V22L6 18H20C21.1 18 22 17.1 22 16V4C22 2.9 21.1 2 20 2Z"
                fill="currentColor"
              />
              <path
                d="M7 9H17M7 13H13"
                stroke="white"
                strokeWidth="2"
                strokeLinecap="round"
              />
            </svg>
            <span className="absolute -top-1 -right-1 w-2.5 h-2.5 bg-amber-400 rounded-full border-2 border-[#2563EB]" />
          </div>

          {/* Logo Tooltip */}
          <div className="absolute left-[78px] px-2.5 py-1 bg-[#1E2230] text-white text-xs font-semibold rounded-lg shadow-lg whitespace-nowrap opacity-0 pointer-events-none group-hover:opacity-100 transition-opacity z-50">
            LinguaFlow
          </div>
        </button>

        {/* Divider */}
        <div className="w-8 h-[1px] bg-[#E8EAF0] dark:bg-[#2A2E3D]" />

        {/* Main Navigation Rail */}
        <nav className="flex flex-col items-center gap-2 w-full px-2" aria-label="Main Menu">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <div key={item.id} className="relative group w-full flex justify-center">
                <button
                  id={`nav-tab-${item.id}`}
                  onClick={() => onTabChange(item.id)}
                  aria-label={item.label}
                  className={`relative flex items-center justify-center w-11 h-11 rounded-xl transition-all ${
                    isActive
                      ? 'bg-[#EFF6FF] dark:bg-[#2563EB]/20 text-[#2563EB] font-medium shadow-sm'
                      : 'text-[#74798C] dark:text-[#9DA3B4] hover:text-[#1E2230] dark:hover:text-[#F5F6FA] hover:bg-[#F7F8FC] dark:hover:bg-[#232630]'
                  }`}
                >
                  <Icon
                    className={`w-5 h-5 transition-transform group-hover:scale-105 ${
                      isActive ? 'stroke-[2.25]' : 'stroke-[1.75]'
                    }`}
                  />

                  {/* Active Indicator on Left Edge */}
                  {isActive && (
                    <span className="absolute -left-2 top-2 bottom-2 w-1 bg-[#2563EB] rounded-r-full" />
                  )}

                  {/* Unread Badge */}
                  {item.badge !== null && item.badge !== undefined && (
                    <span className="absolute -top-1 -right-1 flex items-center justify-center min-w-[18px] h-[18px] px-1 text-[10px] font-bold text-white bg-[#2563EB] rounded-full ring-2 ring-white dark:ring-[#1C1F27]">
                      {item.badge}
                    </span>
                  )}
                </button>

                {/* Floating Tooltip */}
                <div className="absolute left-[68px] top-1/2 -translate-y-1/2 px-2.5 py-1 bg-[#1E2230] dark:bg-[#2A2E3D] text-white text-xs font-medium rounded-lg shadow-lg whitespace-nowrap opacity-0 pointer-events-none group-hover:opacity-100 transition-opacity z-50">
                  {item.label}
                </div>
              </div>
            );
          })}
        </nav>
      </div>

      {/* Bottom Section: Settings & User Profile */}
      <div className="flex flex-col items-center gap-3 w-full px-2">
        {/* Settings Button */}
        <div className="relative group w-full flex justify-center">
          <button
            id="sidebar-settings-btn"
            onClick={onOpenSettings}
            aria-label="Settings"
            className={`flex items-center justify-center w-11 h-11 rounded-xl text-[#74798C] dark:text-[#9DA3B4] hover:text-[#1E2230] dark:hover:text-[#F5F6FA] hover:bg-[#F7F8FC] dark:hover:bg-[#232630] transition-colors ${
              activeTab === 'settings' ? 'bg-[#EFF6FF] dark:bg-[#2563EB]/20 text-[#2563EB]' : ''
            }`}
          >
            <Settings className="w-5 h-5 transition-transform group-hover:rotate-45" />
          </button>
          <div className="absolute left-[68px] top-1/2 -translate-y-1/2 px-2.5 py-1 bg-[#1E2230] dark:bg-[#2A2E3D] text-white text-xs font-medium rounded-lg shadow-lg whitespace-nowrap opacity-0 pointer-events-none group-hover:opacity-100 transition-opacity z-50">
            {t(interfaceLanguage, 'settings')}
          </div>
        </div>

        {/* User Profile Avatar with Popover */}
        <div className="relative">
          <button
            id="sidebar-profile-avatar-btn"
            onClick={() => setProfileOpen(!profileOpen)}
            aria-label={`Profile: ${currentUser.name}`}
            className="relative flex items-center justify-center w-10 h-10 rounded-full ring-2 ring-[#E8EAF0] dark:ring-[#2A2E3D] hover:ring-[#2563EB] transition-all"
          >
            <img
              src={currentUser.avatar}
              alt={currentUser.name}
              className="w-full h-full rounded-full object-cover"
              referrerPolicy="no-referrer"
            />
            <span className="absolute bottom-0 right-0 w-2.5 h-2.5 bg-emerald-500 rounded-full ring-2 ring-white dark:ring-[#1C1F27]" />
          </button>

          {/* Profile Menu Popover */}
          <UserProfileMenu
            user={currentUser}
            settings={settings}
            isOpen={profileOpen}
            onClose={() => setProfileOpen(false)}
            onOpenSettings={onOpenSettings}
            onToggleTheme={onToggleTheme}
            onLogout={onLogout}
            isLoggingOut={isLoggingOut}
          />
        </div>
      </div>
    </aside>
  );
};
