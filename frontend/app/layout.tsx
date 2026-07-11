import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { CONTINUITY_THEME } from "@/lib/continuity";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Holocron",
  description: "Star Wars lore agent: watch it choose between graph traversal and vector search",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
      style={
        {
          // continuity hues have ONE owner (lib/continuity.ts); CSS reads them from here
          "--canon": CONTINUITY_THEME.canon.css,
          "--legends": CONTINUITY_THEME.legends.css,
        } as React.CSSProperties
      }
    >
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
