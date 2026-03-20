"use client";
import { useSession, signOut } from "next-auth/react";
import { Bell, LogOut, Settings, Menu } from "lucide-react";
import Link from "next/link";

interface TopBarProps {
  onMenuToggle?: () => void;
}

function Avatar({ name, image }: { name: string; image?: string | null }) {
  const initials = name.slice(0, 2).toUpperCase();
  if (image) {
    // eslint-disable-next-line @next/next/no-img-element
    return <img src={image} alt={name} className="w-8 h-8 rounded-full border-2 border-saffron/30 object-cover" />;
  }
  return (
    <div className="w-8 h-8 rounded-full bg-saffron/15 border-2 border-saffron/30 flex items-center justify-center text-saffron text-xs font-bold">
      {initials}
    </div>
  );
}

export function TopBar({ onMenuToggle }: TopBarProps) {
  const { data: session } = useSession();
  const name   = session?.user?.name?.split(" ")[0] ?? "there";
  const image  = session?.user?.image;
  const hour   = new Date().getHours();
  const greeting = `${hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening"}, ${name}`;

  return (
    <header className="h-14 flex items-center px-4 md:px-6 border-b border-border bg-background/95 backdrop-blur-sm sticky top-0 z-30">
      {/* Mobile menu button */}
      <button
        onClick={onMenuToggle}
        className="md:hidden p-2 -ml-2 rounded-lg hover:bg-muted transition-colors mr-2"
        aria-label="Open menu"
      >
        <Menu className="w-5 h-5 text-muted-foreground" />
      </button>

      {/* Greeting */}
      <p className="text-sm font-medium text-muted-foreground hidden md:block">
        {greeting}
      </p>

      {/* Right side actions */}
      <div className="flex items-center gap-2 ml-auto">
        {/* Alerts bell */}
        <Link
          href="/alerts"
          className="relative p-2 rounded-lg hover:bg-muted transition-colors"
          aria-label="Alerts"
        >
          <Bell className="w-5 h-5 text-muted-foreground" />
          {/* Dot — shown if HIGH alerts exist */}
          <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-red-500 rounded-full ring-2 ring-background" />
        </Link>

        {/* Settings link */}
        <Link
          href="/settings"
          className="p-2 rounded-lg hover:bg-muted transition-colors hidden md:flex"
          aria-label="Settings"
        >
          <Settings className="w-5 h-5 text-muted-foreground" />
        </Link>

        {/* Avatar with sign-out */}
        <div className="relative group ml-1">
          <button className="focus:outline-none focus:ring-2 focus:ring-saffron/40 rounded-full">
            <Avatar name={name} image={image} />
          </button>
          {/* Dropdown */}
          <div className="absolute right-0 top-full mt-2 w-44 bg-card border border-border rounded-xl shadow-metric py-1 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-150 z-50">
            <div className="px-3 py-2 border-b border-border">
              <p className="text-xs font-semibold text-foreground truncate">{session?.user?.name}</p>
              <p className="text-[11px] text-muted-foreground truncate">{session?.user?.email}</p>
            </div>
            <Link href="/settings" className="flex items-center gap-2 px-3 py-2 text-sm text-foreground hover:bg-muted transition-colors">
              <Settings className="w-4 h-4" /> Settings
            </Link>
            <button
              onClick={() => signOut({ callbackUrl: "/login" })}
              className="flex items-center gap-2 w-full px-3 py-2 text-sm text-red-600 hover:bg-red-50 transition-colors"
            >
              <LogOut className="w-4 h-4" /> Sign out
            </button>
          </div>
        </div>
      </div>
    </header>
  );
}
