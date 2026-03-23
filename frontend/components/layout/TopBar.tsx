"use client";
import { useSession } from "next-auth/react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Bell, Upload, Sun, Moon } from "lucide-react";
import { useEffect, useState } from "react";

const ALERTS_SEEN_KEY = "munim_alerts_seen";

const PAGE_TITLES: Record<string, string> = {
  "/dashboard": "Dashboard",
  "/upload":    "Upload",
  "/reports":   "Reports",
  "/alerts":    "Alerts",
  "/settings":  "Settings",
  "/ca":        "CA Dashboard",
  "/ca/clients":"Clients",
};

function ThemeToggle() {
  const [dark, setDark] = useState(true);

  useEffect(() => {
    const stored = localStorage.getItem("theme");
    const isDark = stored ? stored === "dark" : true;
    setDark(isDark);
    document.documentElement.classList.toggle("light", !isDark);
  }, []);

  function toggle() {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle("light", !next);
    localStorage.setItem("theme", next ? "dark" : "light");
  }

  return (
    <button
      onClick={toggle}
      className="w-9 h-9 flex items-center justify-center rounded-xl text-muted-foreground hover:text-foreground hover:bg-secondary transition-all duration-150"
    >
      {dark ? <Sun className="w-[18px] h-[18px]" /> : <Moon className="w-[18px] h-[18px]" />}
    </button>
  );
}

export function TopBar() {
  const { data: session } = useSession();
  const pathname = usePathname();
  const avatar   = session?.user?.image;
  const name     = session?.user?.name?.split(" ")[0] ?? "User";

  const [alertsSeen, setAlertsSeen] = useState(true);
  useEffect(() => {
    setAlertsSeen(localStorage.getItem(ALERTS_SEEN_KEY) === "true");
  }, []);
  useEffect(() => {
    if (pathname === "/alerts") {
      localStorage.setItem(ALERTS_SEEN_KEY, "true");
      setAlertsSeen(true);
    }
  }, [pathname]);

  const title = PAGE_TITLES[pathname] ?? (
    pathname.startsWith("/analysis/") ? "Analysis" : "Munim"
  );

  return (
    <header className="h-16 bg-card border-b border-border flex items-center justify-between px-6 flex-shrink-0">
      <h1 className="text-xl font-bold text-foreground tracking-tight">{title}</h1>

      <div className="flex items-center gap-2">
        <Link href="/upload" className="btn-primary text-sm px-4 py-2">
          <Upload className="w-4 h-4" />
          Upload
        </Link>

        <ThemeToggle />

        <Link href="/alerts" className="relative w-9 h-9 flex items-center justify-center rounded-xl text-muted-foreground hover:text-foreground hover:bg-secondary transition-all">
          <Bell className="w-[18px] h-[18px]" />
          {!alertsSeen && (
            <span className="absolute top-2 right-2 w-2 h-2 bg-orange-500 rounded-full ring-2 ring-background" />
          )}
        </Link>

        <Link href="/settings" className="ml-1">
          {avatar ? (
            <img src={avatar} className="w-8 h-8 rounded-xl object-cover cursor-pointer ring-2 ring-transparent hover:ring-orange-500 transition-all" alt={name} />
          ) : (
            <div className="w-8 h-8 rounded-xl bg-orange-500 flex items-center justify-center text-white text-sm font-bold cursor-pointer">
              {name[0]}
            </div>
          )}
        </Link>
      </div>
    </header>
  );
}
