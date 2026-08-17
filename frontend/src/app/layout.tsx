import type { Metadata } from "next";
import { Plus_Jakarta_Sans, IBM_Plex_Mono } from "next/font/google";
import { ThemeProvider } from "@/shared/lib/ThemeContext";
import "./globals.css";

const plusJakarta = Plus_Jakarta_Sans({
  subsets: ["latin", "vietnamese"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-plus-jakarta",
  display: "swap",
});

const plexMono = IBM_Plex_Mono({
  subsets: ["latin", "latin-ext", "vietnamese"],
  weight: ["400", "500"],
  variable: "--font-plex-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "LinguaFlow",
  description:
    "Chat in your language, they read in theirs. Real-time translation across 14 languages.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    // The script below writes data-theme onto this element before React
    // hydrates, so the attribute is always present on the client and never in
    // the server HTML. That difference is the whole point of the script — it is
    // what stops a light flash before the saved theme applies — so the warning
    // it would otherwise raise is suppressed here rather than worked around.
    <html
      lang="en"
      dir="ltr"
      className={`${plusJakarta.variable} ${plexMono.variable}`}
      suppressHydrationWarning
    >
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `
              (function() {
                try {
                  var interfaceLanguage = localStorage.getItem('interface_language');
                  var supportedLanguages = [
                    'en', 'vi', 'ja', 'zh', 'ko', 'fr', 'de', 'es', 'th',
                    'id', 'pt', 'ru', 'ar', 'hi'
                  ];
                  if (supportedLanguages.indexOf(interfaceLanguage) !== -1) {
                    document.documentElement.lang = interfaceLanguage;
                    document.documentElement.dir = interfaceLanguage === 'ar' ? 'rtl' : 'ltr';
                  } else {
                    document.documentElement.dir = 'ltr';
                  }

                  // Only an explicit choice is written. "system" deliberately
                  // leaves the attribute off so the prefers-color-scheme media
                  // query decides, which is exactly what ThemeContext does —
                  // setting it here too would make the two disagree.
                  var saved = localStorage.getItem('lingua_theme_mode');
                  if (saved === 'dark' || saved === 'light') {
                    document.documentElement.setAttribute('data-theme', saved);
                  }
                } catch (e) {}
              })();
            `,
          }}
        />
      </head>
      <body>
        <ThemeProvider>{children}</ThemeProvider>
      </body>
    </html>
  );
}

