import type { Metadata } from "next";
import { Be_Vietnam_Pro, IBM_Plex_Mono } from "next/font/google";
import "./globals.css";

/* Be Vietnam Pro thay Inter: dấu thanh tiếng Việt không chồng lên chữ hoa
   (Ậ, Ỗ, Ừ), hẹp hơn nên chịu được mật độ, và không phải chữ ký của giao
   diện sinh tự động. Cả hai đều là font tĩnh nên phải khai báo weight. */
const beVietnam = Be_Vietnam_Pro({
  subsets: ["latin", "latin-ext", "vietnamese"],
  weight: ["400", "500", "600"],
  variable: "--font-be-vietnam",
  display: "swap",
});

const plexMono = IBM_Plex_Mono({
  subsets: ["latin", "latin-ext", "vietnamese"],
  weight: ["400", "500"],
  variable: "--font-plex-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "LinguaChat",
  description:
    "Nhắn tin bằng tiếng của bạn, người kia đọc bằng tiếng của họ. Dịch tự động 10 ngôn ngữ.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="vi" className={`${beVietnam.variable} ${plexMono.variable}`}>
      <body>{children}</body>
    </html>
  );
}
