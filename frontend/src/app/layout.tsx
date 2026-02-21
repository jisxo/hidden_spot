import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Hidden Spot | AI 맛집 큐레이션",
  description: "네이버 지도 링크 하나로 AI가 분석하는 나만의 맛집 지도",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ko" suppressHydrationWarning>
      <head>
        <link rel="preconnect" href="https://openapi.map.naver.com" crossOrigin="" />
        <link rel="dns-prefetch" href="//openapi.map.naver.com" />
      </head>
      <body className="font-sans" suppressHydrationWarning>
        {children}
      </body>
    </html>
  );
}
