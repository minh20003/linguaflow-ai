"use client";

import React, { useCallback, useEffect, useState } from "react";
import { AlertCircle, Link2, Link2Off, RefreshCw } from "lucide-react";
import type { ApiCalendarCapability } from "../api/chat-api";
import {
  getGoogleCalendarStatus,
  startGoogleCalendarLink,
  syncGoogleCalendarNow,
  unlinkGoogleCalendar,
} from "../api/chat-api";
import { useT } from "../language-context";

interface GoogleCalendarControlsProps {
  token: string;
  onSynced?: () => void;
  onNotify?: (title: string, detail?: string, tone?: "success" | "warning") => void;
}

/** Connect, sync and disconnect a Google Calendar — shown only when it applies.
 *
 *  The component renders one of four states, and choosing between them is the
 *  whole point of it:
 *
 *  - The deployment has no Google credentials: render **nothing**. A control
 *    for a feature that cannot exist here would promise something and then
 *    answer 503.
 *  - Configured but the user has not granted `calendar_read`: point at the
 *    permission rather than at a connect button, because connecting is what
 *    the permission is for.
 *  - Permitted but not linked: offer to connect.
 *  - Linked: offer to sync now and to disconnect, and show the last failure if
 *    there was one.
 *
 *  Before this existed the calendar showed a "Google" button unconditionally,
 *  left over from the mock, which answered with an error and gave the user
 *  nowhere to go.
 */
export const GoogleCalendarControls: React.FC<GoogleCalendarControlsProps> = ({
  token,
  onSynced,
  onNotify,
}) => {
  const ui = useT();
  const [status, setStatus] = useState<ApiCalendarCapability | null>(null);
  const [isBusy, setIsBusy] = useState(false);

  const refresh = useCallback(async () => {
    try {
      setStatus(await getGoogleCalendarStatus(token));
    } catch {
      // Treated as "not available" rather than surfaced. This is a capability
      // probe, and failing it should quietly hide the controls rather than put
      // an error in front of somebody who was not asking about Google at all.
      setStatus(null);
    }
  }, [token]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  if (!status?.configured) return null;

  const connect = async () => {
    setIsBusy(true);
    try {
      const { authorization_url } = await startGoogleCalendarLink(token);
      // A full navigation rather than a popup: Google blocks its consent screen
      // in many embedded contexts, and a popup that silently fails to open
      // looks like a broken button.
      window.location.href = authorization_url;
    } catch (error) {
      onNotify?.(
        ui("Unable to open Google authorization page"),
        error instanceof Error ? error.message : undefined,
        "warning",
      );
      setIsBusy(false);
    }
  };

  const syncNow = async () => {
    setIsBusy(true);
    try {
      const result = await syncGoogleCalendarNow(token);
      onSynced?.();
      await refresh();
      if (result.last_sync_error) {
        onNotify?.(ui("Sync incomplete"), result.last_sync_error, "warning");
      } else {
        onNotify?.(
          ui("Google Calendar synced"),
          `Đẩy lên ${result.pushed}, nhận về ${result.pulled}`,
          "success",
        );
      }
    } catch (error) {
      onNotify?.(
        ui("Sync failed"),
        error instanceof Error ? error.message : undefined,
        "warning",
      );
    } finally {
      setIsBusy(false);
    }
  };

  const disconnect = async () => {
    setIsBusy(true);
    try {
      await unlinkGoogleCalendar(token);
      await refresh();
      // Said explicitly because it is the surprising half: unlinking removes
      // this app's access, it does not remove appointments already in Google.
      onNotify?.(
        ui("Google Calendar disconnected"),
        ui("Synced events will remain in your Google Calendar."),
        "success",
      );
    } catch (error) {
      onNotify?.(
        ui("Unable to disconnect"),
        error instanceof Error ? error.message : undefined,
        "warning",
      );
    } finally {
      setIsBusy(false);
    }
  };

  if (!status.consented) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-medium text-amber-800 dark:border-amber-400/30 dark:bg-amber-500/10 dark:text-amber-200">
        <AlertCircle className="h-3.5 w-3.5 flex-none" />
        Bật quyền &ldquo;Đọc lịch Google&rdquo; trong Cài đặt → Trợ lý để kết nối
      </span>
    );
  }

  if (!status.linked) {
    return (
      <button
        type="button"
        onClick={() => void connect()}
        disabled={isBusy}
        className="inline-flex items-center gap-1.5 rounded-xl border border-sky-200 bg-sky-50 px-3 py-2 text-xs font-semibold text-sky-700 hover:bg-sky-100 disabled:opacity-50 dark:border-sky-400/30 dark:bg-sky-500/10 dark:text-sky-300"
      >
        <Link2 className="h-4 w-4" />
        Kết nối Google Calendar
      </button>
    );
  }

  return (
    <span className="inline-flex items-center gap-1.5">
      <button
        type="button"
        onClick={() => void syncNow()}
        disabled={isBusy}
        title={
          status.last_synced_at
            ? `Lần cuối: ${new Date(status.last_synced_at).toLocaleString("vi-VN")}`
            : ui("Never synced")
        }
        className="inline-flex items-center gap-1.5 rounded-xl border border-sky-200 bg-sky-50 px-3 py-2 text-xs font-semibold text-sky-700 hover:bg-sky-100 disabled:opacity-50 dark:border-sky-400/30 dark:bg-sky-500/10 dark:text-sky-300"
      >
        <RefreshCw className={`h-4 w-4 ${isBusy ? "animate-spin" : ""}`} />
        {isBusy ? ui("Syncing") : ui("Sync now")}
      </button>
      <button
        type="button"
        onClick={() => void disconnect()}
        disabled={isBusy}
        title={ui("Disconnect Google Calendar")}
        aria-label={ui("Disconnect Google Calendar")}
        className="rounded-xl border border-[#E8EAF0] px-2 py-2 text-[#74798C] hover:bg-[#F7F8FC] disabled:opacity-50 dark:border-[#2E3342] dark:hover:bg-[#232630]"
      >
        <Link2Off className="h-4 w-4" />
      </button>
      {status.last_sync_error && (
        <span
          title={status.last_sync_error}
          className="inline-flex items-center gap-1 text-[11px] font-medium text-rose-600 dark:text-rose-300"
        >
          <AlertCircle className="h-3.5 w-3.5 flex-none" />
          Lần đồng bộ trước lỗi
        </span>
      )}
    </span>
  );
};
