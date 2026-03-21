import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { Providers } from "@/components/layout/Providers";

const geistSans = Geist({
  subsets:  ["latin"],
  variable: "--font-geist-sans",
  display:  "swap",
});

const geistMono = Geist_Mono({
  subsets:  ["latin"],
  variable: "--font-geist-mono",
  display:  "swap",
});

export const metadata: Metadata = {
  title:       { default: "Munim — AI Business Intelligence", template: "%s | Munim" },
  description: "AI-powered business intelligence for Indian small businesses.",
  icons:       { icon: "/favicon.ico" },
};

// Runs before React hydration to prevent flash
const themeScript = `
  try {
    const t = localStorage.getItem('theme');
    if (t === 'light') document.documentElement.classList.add('light');
  } catch(e) {}
`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable}`} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
