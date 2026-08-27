import React, { useEffect, useState } from 'react';
import { Download, FileText, Image as ImageIcon, LoaderCircle, Volume2 } from 'lucide-react';
import { interactionText } from '../i18n';
import type { LanguageCode, MessageAttachment } from '../types';

interface MessageAttachmentCardProps {
  attachment: MessageAttachment;
  language: LanguageCode;
  onDownload: (attachment: MessageAttachment) => void;
  onLoadPreview: (attachment: MessageAttachment) => Promise<string>;
}

export const MessageAttachmentCard: React.FC<MessageAttachmentCardProps> = ({
  attachment,
  language,
  onDownload,
  onLoadPreview,
}) => {
  const [previewUrl, setPreviewUrl] = useState<string>();
  const [previewFailed, setPreviewFailed] = useState(false);
  const isImage = attachment.type === 'image';
  const isAudio = attachment.type === 'audio';
  const shouldLoadPreview = isImage || isAudio;

  useEffect(() => {
    if (!shouldLoadPreview) return;
    let active = true;
    let objectUrl: string | undefined;
    setPreviewUrl(undefined);
    setPreviewFailed(false);
    void onLoadPreview(attachment)
      .then((url) => {
        objectUrl = url;
        if (active) setPreviewUrl(url);
        else URL.revokeObjectURL(url);
      })
      .catch(() => {
        if (active) setPreviewFailed(true);
      });
    return () => {
      active = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [attachment, onLoadPreview, shouldLoadPreview]);

  return (
    <article className="w-[min(21rem,72vw)] overflow-hidden rounded-xl border border-[#DDE1EA] bg-white text-[#1E2230] shadow-sm dark:border-[#34394A] dark:bg-[#232630] dark:text-[#F5F6FA]">
      {isImage && (
        <button
          type="button"
          onClick={() => onDownload(attachment)}
          aria-label={`${interactionText(language, 'Download file')}: ${attachment.name}`}
          className="relative flex h-48 w-full items-center justify-center overflow-hidden bg-[#F4F5F8] dark:bg-[#1C1F27]"
        >
          {previewUrl ? (
            <img src={previewUrl} alt={attachment.name} className="h-full w-full object-cover transition-transform duration-200 hover:scale-[1.02]" />
          ) : previewFailed ? (
            <ImageIcon className="h-10 w-10 text-[#9DA3B4]" />
          ) : (
            <LoaderCircle className="h-6 w-6 animate-spin text-[#2563EB]" />
          )}
        </button>
      )}

      {isAudio && (
        <div className="flex min-h-16 w-full items-center justify-center bg-[#F7F8FC] p-3 dark:bg-[#1C1F27]">
          {previewUrl ? (
            <audio
              controls
              preload="metadata"
              src={previewUrl}
              aria-label={interactionText(language, 'Voice message')}
              className="h-10 w-full"
            />
          ) : previewFailed ? (
            <Volume2 className="h-7 w-7 text-[#9DA3B4]" />
          ) : (
            <LoaderCircle className="h-6 w-6 animate-spin text-[#2563EB]" />
          )}
        </div>
      )}

      <button
        type="button"
        onClick={() => onDownload(attachment)}
        aria-label={`${interactionText(language, 'Download file')}: ${attachment.name}`}
        className="group flex w-full items-center gap-3 p-3 text-left hover:bg-[#F7F8FC] dark:hover:bg-[#2A2E3D]"
      >
        <span className={`flex h-10 w-10 flex-none items-center justify-center rounded-lg ${isImage ? 'bg-violet-50 text-violet-600 dark:bg-violet-500/15 dark:text-violet-300' : isAudio ? 'bg-rose-50 text-rose-600 dark:bg-rose-500/15 dark:text-rose-300' : 'bg-[#EFF6FF] text-[#2563EB] dark:bg-[#2563EB]/20 dark:text-[#60A5FA]'}`}>
          {isImage ? <ImageIcon className="h-5 w-5" /> : isAudio ? <Volume2 className="h-5 w-5" /> : <FileText className="h-5 w-5" />}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-semibold">
            {isAudio ? interactionText(language, 'Voice message') : attachment.name}
          </span>
          <span className="block text-[11px] text-[#74798C] dark:text-[#9DA3B4]">{attachment.size}</span>
        </span>
        <span className="flex h-8 w-8 flex-none items-center justify-center rounded-lg text-[#74798C] group-hover:bg-[#EFF6FF] group-hover:text-[#2563EB] dark:group-hover:bg-[#2563EB]/20 dark:group-hover:text-[#60A5FA]">
          <Download className="h-4 w-4" />
        </span>
      </button>
    </article>
  );
};
