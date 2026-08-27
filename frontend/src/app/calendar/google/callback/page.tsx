"use client";

import React, { Suspense, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { CalendarCheck, CircleAlert, Loader2 } from "lucide-react";
import { completeGoogleCalendarLink } from "@/features/chat/api/chat-api";
import { getAccessToken } from "@/shared/lib/session";

type Phase = "working" | "done" | "failed";

/** Where Google sends the user back after the consent screen.
 *
 *  The path must match `GOOGLE_OAUTH_REDIRECT_URI` and the Console entry
 *  exactly; a mismatch is refused by Google before this page is ever reached.
 *
 *  The page hands `code` and `state` straight to the backend and shows nothing
 *  else. The exchange needs the client secret, which belongs on the server —
 *  doing it here would mean shipping that secret to every browser.
 */
function CallbackInner() {
  const router = useRouter();
  const params = useSearchParams();

  // Everything decidable without a network call is decided during render.
  // Putting these in the effect meant calling setState synchronously inside it,
  // which fights how React batches and is what `set-state-in-effect` warns
  // about; only the exchange genuinely has to wait for anything.
  const denied = params.get("error");
  const code = params.get("code");
  const state = params.get("state");
  // Lazy initialiser: `getAccessToken` reads browser storage, which does not
  // exist while the tree is being prerendered.
  const [token] = useState(() => getAccessToken());

  const upfrontProblem = denied
    ? // Declining is a choice, not a failure. Said plainly rather than as an
      // error that invites them to try the same thing again.
      "Bạn đã từ chối cấp quyền, nên lịch chưa được kết nối."
    : !code || !state
      ? "Liên kết trả về thiếu thông tin. Hãy thử kết nối lại từ trang lịch."
      : !token
        ? "Phiên đăng nhập đã hết hạn. Hãy đăng nhập lại rồi thử kết nối lần nữa."
        : null;

  const [phase, setPhase] = useState<Phase>(upfrontProblem ? "failed" : "working");
  const [detail, setDetail] = useState<string>(upfrontProblem ?? "");
  // React runs effects twice in development. An authorization code is
  // single-use, so a second attempt would fail and overwrite a link that had
  // just succeeded with an error message.
  const started = useRef(false);

  useEffect(() => {
    if (upfrontProblem || started.current || !code || !state || !token) return;
    started.current = true;

    completeGoogleCalendarLink(token, code, state)
      .then(() => {
        setPhase("done");
        window.setTimeout(() => router.replace("/chat"), 1500);
      })
      .catch((error: unknown) => {
        setPhase("failed");
        setDetail(error instanceof Error ? error.message : "Không hoàn tất được kết nối.");
      });
  }, [code, state, token, upfrontProblem, router]);

  return (
    <main className="flex min-h-screen items-center justify-center bg-[#F7F8FC] p-6 dark:bg-[#14161C]">
      <div className="w-full max-w-md rounded-3xl bg-white p-8 text-center shadow-sm dark:bg-[#1C1F27]">
        {phase === "working" && (
          <>
            <Loader2 className="mx-auto h-10 w-10 animate-spin text-[#2563EB]" />
            <h1 className="mt-4 text-base font-bold text-[#1E2230] dark:text-[#F5F6FA]">
              Đang kết nối Google Calendar…
            </h1>
          </>
        )}

        {phase === "done" && (
          <>
            <CalendarCheck className="mx-auto h-10 w-10 text-emerald-600" />
            <h1 className="mt-4 text-base font-bold text-[#1E2230] dark:text-[#F5F6FA]">
              Đã kết nối
            </h1>
            <p className="mt-2 text-xs leading-relaxed text-[#74798C] dark:text-[#9DA3B4]">
              Việc bạn duyệt sẽ được thêm vào Google Calendar, và thay đổi bên đó sẽ hiện
              về đây. Đang đưa bạn trở lại…
            </p>
          </>
        )}

        {phase === "failed" && (
          <>
            <CircleAlert className="mx-auto h-10 w-10 text-amber-600" />
            <h1 className="mt-4 text-base font-bold text-[#1E2230] dark:text-[#F5F6FA]">
              Chưa kết nối được
            </h1>
            <p className="mt-2 text-xs leading-relaxed text-[#74798C] dark:text-[#9DA3B4]">
              {detail}
            </p>
            <button
              type="button"
              onClick={() => router.replace("/chat")}
              className="mt-5 rounded-xl bg-[#2563EB] px-4 py-2 text-xs font-bold text-white hover:bg-[#1D4FD7]"
            >
              Quay lại ứng dụng
            </button>
          </>
        )}
      </div>
    </main>
  );
}

export default function GoogleCalendarCallbackPage() {
  // `useSearchParams` forces this subtree to be client-rendered; without the
  // boundary the whole route fails to prerender at build time.
  return (
    <Suspense fallback={null}>
      <CallbackInner />
    </Suspense>
  );
}
