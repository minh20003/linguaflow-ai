import React from 'react';
import {
  CalendarRange,
  ChevronDown,
  Menu,
  RotateCw,
} from 'lucide-react';
import { AdminTab, TimeRangeFilter } from '../types';

interface HeaderProps {
  currentTab: AdminTab;
  interfaceLanguage: 'vi' | 'en';
  timeRange: TimeRangeFilter;
  onTimeRangeChange: (range: TimeRangeFilter) => void;
  onRefresh: () => void;
  isRefreshing?: boolean;
  onToggleMobileSidebar: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  currentTab,
  interfaceLanguage,
  timeRange,
  onTimeRangeChange,
  onRefresh,
  isRefreshing = false,
  onToggleMobileSidebar,
}) => {
  const getTabTitle = () => {
    const vi = interfaceLanguage === 'vi';
    switch (currentTab) {
      case 'analytics':
        return vi ? 'Trung tâm quản trị' : 'Admin center';
      case 'feedback':
        return vi ? 'Phản hồi bản dịch' : 'Translation feedback';
      case 'glossary':
        return vi ? 'Quản lý thuật ngữ' : 'Glossary management';
      case 'suggestions':
        return vi ? 'Kiểm duyệt đề xuất' : 'Suggestion review';
      case 'chat':
        return vi ? 'Trò chuyện & Dịch thuật' : 'Chat & Translation';
      default:
        return vi ? 'Trung tâm quản trị' : 'Admin center';
    }
  };

  return (
    <header
      id="admin-header"
      className="h-16 bg-white border-b border-gray-200 px-4 sm:px-8 flex items-center justify-between sticky top-0 z-30"
    >
      {/* Left: Mobile menu toggle + Page title */}
      <div className="flex items-center gap-3">
        <button
          id="mobile-sidebar-toggle"
          onClick={onToggleMobileSidebar}
          className="p-1.5 -ml-1 text-gray-600 hover:text-gray-900 rounded-md hover:bg-gray-100 lg:hidden"
          aria-label="Toggle Sidebar"
        >
          <Menu className="w-5 h-5" />
        </button>

        <h1 className="text-lg sm:text-xl font-semibold text-gray-900 tracking-tight">
          {getTabTitle()}
        </h1>
      </div>

      {/* Right: Actions, Filters, Profile */}
      <div className="flex items-center gap-3">
        {/* Time Range Filter (In Analytics) */}
        {currentTab === 'analytics' && (
          <label className="relative hidden items-center sm:flex" htmlFor="filter-time-range">
            <CalendarRange className="pointer-events-none absolute left-3 h-4 w-4 text-blue-600" />
            <span className="sr-only">{interfaceLanguage === 'vi' ? 'Chọn khoảng thời gian' : 'Select time range'}</span>
            <select
              id="filter-time-range"
              value={timeRange}
              onChange={(event) => onTimeRangeChange(event.target.value as TimeRangeFilter)}
              className="h-9 min-w-36 appearance-none rounded-lg border border-gray-200 bg-white py-1.5 pl-9 pr-9 text-sm font-semibold text-gray-700 outline-none transition-colors hover:border-blue-300 focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
              aria-label={interfaceLanguage === 'vi' ? 'Khoảng thời gian thống kê' : 'Analytics time range'}
            >
              <option value="24h">{interfaceLanguage === 'vi' ? '24 giờ qua' : 'Last 24 hours'}</option>
              <option value="7d">{interfaceLanguage === 'vi' ? '7 ngày qua' : 'Last 7 days'}</option>
              <option value="30d">{interfaceLanguage === 'vi' ? '30 ngày qua' : 'Last 30 days'}</option>
              <option value="all">{interfaceLanguage === 'vi' ? 'Tất cả' : 'All time'}</option>
            </select>
            <ChevronDown className="pointer-events-none absolute right-3 h-4 w-4 text-gray-500" />
          </label>
        )}

        {/* Refresh Button */}
        <button
          id="btn-refresh-data"
          onClick={onRefresh}
          title={interfaceLanguage === 'vi' ? 'Làm mới dữ liệu' : 'Refresh data'}
          className="p-2 text-gray-500 hover:text-gray-900 rounded-md hover:bg-gray-100 border border-gray-200 transition-colors"
        >
          <RotateCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin text-blue-600' : ''}`} />
        </button>

      </div>
    </header>
  );
};
