import React from 'react';
import { Conversation, User } from '../types';
import {
  X,
  Bell,
  BellOff,
  ShieldAlert,
  LogOut,
  UsersRound,
  Globe,
  Pin
} from 'lucide-react';

interface ConversationDetailsDrawerProps {
  conversation: Conversation;
  isOpen: boolean;
  onClose: () => void;
  onToggleMute: (conversationId: string) => void;
  onTogglePin?: (conversationId: string) => void;
}

export const ConversationDetailsDrawer: React.FC<ConversationDetailsDrawerProps> = ({
  conversation,
  isOpen,
  onClose,
  onToggleMute,
  onTogglePin,
}) => {
  if (!isOpen) return null;

  const isGroup = conversation.type === 'group';

  return (
    <aside
      id="conversation-details-drawer"
      className="w-80 sm:w-88 h-screen bg-white dark:bg-[#1C1F27] border-l border-[#E8EAF0] dark:border-[#232630] flex flex-col z-30 shadow-xl overflow-y-auto flex-shrink-0 animate-in slide-in-from-right duration-200"
      aria-label="Conversation Details"
    >
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-[#E8EAF0] dark:border-[#232630]">
        <h3 className="text-base font-bold text-[#1E2230] dark:text-[#F5F6FA]">
          {isGroup ? 'Group Information' : 'Contact Details'}
        </h3>
        <button
          id="close-details-drawer-btn"
          onClick={onClose}
          aria-label="Close details"
          className="p-1.5 rounded-xl text-[#74798C] hover:text-[#1E2230] dark:hover:text-white hover:bg-[#F7F8FC] dark:hover:bg-[#232630] transition-colors"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Main Profile Info */}
      <div className="flex flex-col items-center p-6 text-center border-b border-[#E8EAF0] dark:border-[#232630]">
        <div className="relative mb-3">
          <img
            src={conversation.avatar}
            alt={conversation.name}
            className="w-20 h-20 rounded-full object-cover ring-4 ring-[#EFF6FF] dark:ring-[#2563EB]/20"
            referrerPolicy="no-referrer"
          />
          {conversation.isOnline && !isGroup && (
            <span className="absolute bottom-1 right-1 w-4 h-4 bg-emerald-500 rounded-full ring-2 ring-white dark:ring-[#1C1F27]" />
          )}
        </div>

        <h4 className="text-lg font-bold text-[#1E2230] dark:text-[#F5F6FA]">
          {conversation.name}
        </h4>

        {conversation.recipient && (
          <p className="text-xs text-[#74798C] dark:text-[#9DA3B4] mt-0.5">
            @{conversation.recipient.username}
          </p>
        )}

        {conversation.description && (
          <p className="text-xs text-[#74798C] dark:text-[#9DA3B4] mt-2 max-w-xs leading-relaxed">
            {conversation.description}
          </p>
        )}

        {/* Language Badge */}
        {conversation.recipient && (
          <div className="inline-flex items-center gap-1.5 mt-3 px-3 py-1 bg-[#EFF6FF] dark:bg-[#2563EB]/20 text-[#2563EB] text-xs font-semibold rounded-full">
            <Globe className="w-3.5 h-3.5" />
            <span>Native Language: {conversation.recipient.nativeLanguage.toUpperCase()}</span>
          </div>
        )}

        {isGroup && (
          <div className="inline-flex items-center gap-1.5 mt-3 px-3 py-1 bg-[#EFF6FF] dark:bg-[#2563EB]/20 text-[#2563EB] text-xs font-semibold rounded-full">
            <UsersRound className="w-3.5 h-3.5" />
            <span>{conversation.memberCount || 8} Global Members</span>
          </div>
        )}
      </div>

      {/* Quick Action Toggles */}
      <div className="p-4 space-y-1 border-b border-[#E8EAF0] dark:border-[#232630]">
        <button
          onClick={() => onToggleMute(conversation.id)}
          className="w-full flex items-center justify-between px-3 py-2.5 rounded-xl hover:bg-[#F7F8FC] dark:hover:bg-[#232630] transition-colors text-left text-xs text-[#1E2230] dark:text-[#E2E5F0]"
        >
          <div className="flex items-center gap-3">
            {conversation.isMuted ? (
              <BellOff className="w-4 h-4 text-amber-500" />
            ) : (
              <Bell className="w-4 h-4 text-[#74798C]" />
            )}
            <span>Mute Notifications</span>
          </div>
          <span className="font-medium text-[#74798C]">
            {conversation.isMuted ? 'Muted' : 'Off'}
          </span>
        </button>

        {onTogglePin && (
          <button
            onClick={() => onTogglePin(conversation.id)}
            className="w-full flex items-center justify-between px-3 py-2.5 rounded-xl hover:bg-[#F7F8FC] dark:hover:bg-[#232630] transition-colors text-left text-xs text-[#1E2230] dark:text-[#E2E5F0]"
          >
            <div className="flex items-center gap-3">
              <Pin className="w-4 h-4 text-[#74798C]" />
              <span>Pin Conversation</span>
            </div>
            <span className="font-medium text-[#74798C]">
              {conversation.isPinned ? 'Pinned' : 'No'}
            </span>
          </button>
        )}
      </div>

      {/* Group Members List (If Group) */}
      {isGroup && conversation.members && (
        <div className="p-4 border-b border-[#E8EAF0] dark:border-[#232630]">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-bold uppercase tracking-wider text-[#74798C] dark:text-[#9DA3B4]">
              Members ({conversation.members.length})
            </span>
          </div>
          <div className="space-y-2">
            {conversation.members.map((member) => (
              <div key={member.id} className="flex items-center justify-between text-xs py-1">
                <div className="flex items-center gap-2.5 min-w-0">
                  <img
                    src={member.avatar}
                    alt={member.name}
                    className="w-7 h-7 rounded-full object-cover"
                    referrerPolicy="no-referrer"
                  />
                  <div className="min-w-0">
                    <p className="font-semibold text-[#1E2230] dark:text-[#F5F6FA] truncate">
                      {member.name}
                    </p>
                    <p className="text-[10px] text-[#74798C] dark:text-[#9DA3B4] truncate">
                      {member.role || 'Member'}
                    </p>
                  </div>
                </div>
                <span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-[#F4F5F8] dark:bg-[#2A2E3D] text-[#2563EB]">
                  {member.nativeLanguage.toUpperCase()}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Danger Zone */}
      <div className="p-4 border-t border-[#E8EAF0] dark:border-[#232630] mt-auto">
        {isGroup ? (
          <button className="w-full flex items-center justify-center gap-2 py-2.5 text-xs font-semibold text-rose-600 dark:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-950/30 rounded-xl transition-colors">
            <LogOut className="w-4 h-4" />
            <span>Leave Group</span>
          </button>
        ) : (
          <button className="w-full flex items-center justify-center gap-2 py-2.5 text-xs font-semibold text-rose-600 dark:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-950/30 rounded-xl transition-colors">
            <ShieldAlert className="w-4 h-4" />
            <span>Block Contact</span>
          </button>
        )}
      </div>
    </aside>
  );
};
