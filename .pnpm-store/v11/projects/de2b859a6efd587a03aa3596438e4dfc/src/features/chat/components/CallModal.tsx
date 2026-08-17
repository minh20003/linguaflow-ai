import React, { useState, useEffect } from 'react';
import { Conversation } from '../types';
import { PhoneOff, Mic, MicOff, Video, VideoOff, Volume2, Sparkles, Globe } from 'lucide-react';

interface CallModalProps {
  isOpen: boolean;
  type: 'voice' | 'video';
  conversation: Conversation;
  onEndCall: () => void;
}

export const CallModal: React.FC<CallModalProps> = ({
  isOpen,
  type,
  conversation,
  onEndCall,
}) => {
  const [isMuted, setIsMuted] = useState(false);
  const [isVideoOff, setIsVideoOff] = useState(false);
  const [callSeconds, setCallSeconds] = useState(0);

  useEffect(() => {
    if (!isOpen) {
      setCallSeconds(0);
      return;
    }
    const interval = setInterval(() => {
      setCallSeconds((prev) => prev + 1);
    }, 1000);
    return () => clearInterval(interval);
  }, [isOpen]);

  if (!isOpen) return null;

  const formatDuration = (sec: number) => {
    const mins = Math.floor(sec / 60);
    const s = sec % 60;
    return `${mins.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  };

  return (
    <div
      id="call-modal-backdrop"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-in fade-in duration-200"
    >
      <div
        id="active-call-card"
        className="relative w-full max-w-lg bg-[#1C1F27] text-white rounded-3xl overflow-hidden shadow-2xl border border-[#2A2E3D] flex flex-col items-center p-8 text-center"
      >
        {/* Real-time speech translation badge */}
        <div className="inline-flex items-center gap-1.5 px-3 py-1 bg-[#2563EB]/20 border border-[#2563EB]/40 rounded-full text-xs text-[#60A5FA] mb-6">
          <Sparkles className="w-3.5 h-3.5" />
          <span>Live Voice Translation Active</span>
        </div>

        {/* Avatar / Video Preview */}
        <div className="relative mb-6">
          {type === 'video' && !isVideoOff ? (
            <div className="w-48 h-48 rounded-3xl overflow-hidden ring-4 ring-[#2563EB] shadow-2xl relative">
              <img
                src={conversation.avatar}
                alt={conversation.name}
                className="w-full h-full object-cover"
                referrerPolicy="no-referrer"
              />
              <div className="absolute bottom-2 left-2 right-2 bg-black/60 backdrop-blur-xs px-2 py-1 rounded-lg text-[10px] text-emerald-400 font-mono">
                HD 1080p • Encrypted
              </div>
            </div>
          ) : (
            <div className="relative">
              <img
                src={conversation.avatar}
                alt={conversation.name}
                className="w-28 h-28 rounded-full object-cover ring-4 ring-[#2563EB]/40 shadow-xl"
                referrerPolicy="no-referrer"
              />
              {/* Waveform ripple pulse */}
              <span className="absolute inset-0 rounded-full ring-2 ring-[#2563EB] animate-ping opacity-30" />
            </div>
          )}
        </div>

        {/* Contact Info */}
        <h3 className="text-xl font-bold mb-1">{conversation.name}</h3>
        <p className="text-xs text-[#9DA3B4] font-mono mb-6">
          {formatDuration(callSeconds)}
        </p>

        {/* Live Subtitle Stream Simulation */}
        <div className="w-full max-w-sm p-3.5 bg-[#232630] rounded-2xl border border-[#2A2E3D] text-xs text-left mb-8 shadow-inner">
          <div className="flex items-center gap-1.5 text-[10px] font-bold text-[#2563EB] uppercase mb-1">
            <Globe className="w-3 h-3" />
            <span>Simultaneous Audio Translation:</span>
          </div>
          <p className="text-[#F5F6FA] italic leading-relaxed">
            "We are reviewing the final presentation slides now..."
          </p>
        </div>

        {/* Control Buttons */}
        <div className="flex items-center gap-4">
          <button
            onClick={() => setIsMuted(!isMuted)}
            className={`p-4 rounded-full transition-all ${
              isMuted
                ? 'bg-rose-500 text-white'
                : 'bg-[#2A2E3D] hover:bg-[#34394B] text-[#F5F6FA]'
            }`}
          >
            {isMuted ? <MicOff className="w-6 h-6" /> : <Mic className="w-6 h-6" />}
          </button>

          {type === 'video' && (
            <button
              onClick={() => setIsVideoOff(!isVideoOff)}
              className={`p-4 rounded-full transition-all ${
                isVideoOff
                  ? 'bg-rose-500 text-white'
                  : 'bg-[#2A2E3D] hover:bg-[#34394B] text-[#F5F6FA]'
              }`}
            >
              {isVideoOff ? <VideoOff className="w-6 h-6" /> : <Video className="w-6 h-6" />}
            </button>
          )}

          <button
            onClick={onEndCall}
            className="p-4 rounded-full bg-rose-600 hover:bg-rose-700 text-white shadow-lg shadow-rose-600/30 hover:scale-105 active:scale-95 transition-all"
          >
            <PhoneOff className="w-6 h-6" />
          </button>
        </div>
      </div>
    </div>
  );
};
