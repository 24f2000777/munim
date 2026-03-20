import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { Geist_Mono } from "next/font/google";
import "./globals.css";
import { Providers } from "@/components/layout/Providers";

const inter = Inter({
  subsets:  ["latin"],
  variable: "--font-inter",
  display:  "swap",
});

const geistMono = Geist_Mono({
  subsets:  ["latin"],
  variable: "--font-geist-mono",
  display:  "swap",
});

export const metadata: Metadata = {
  title:       { default: "Munim — AI Business Intelligence", template: "%s | Munim" },
  description: "Weekly WhatsApp business reports in Hindi and English for Indian small businesses.",
  icons:       { icon: "/favicon.ico" },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="hi" className={`${inter.variable} ${geistMono.variable}`}>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
