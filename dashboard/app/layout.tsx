import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "PPE Watchman",
  description: "산업 현장 PPE 위반 실시간 모니터링",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
