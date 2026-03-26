"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSession, signOut } from "next-auth/react";
import { useEffect, useState } from "react";
import {
  LayoutDashboard, Upload, FileText, Bell,
  Settings, Users, LogOut, TrendingUp, ChevronRight,
} from "lucide-react";
import { cn } from "@/lib/utils";

const ALERTS_SEEN_KEY = "munim_alerts_seen";

const NAV = [
  { href: "/dashboard", icon: LayoutDashboard, label: "Dashboard" },
  { href: "/upload",    icon: Upload,           label: "Upload"    },
  { href: "/reports",   icon: FileText,          label: "Reports"   },
  { href: "/alerts",    icon: Bell,              label: "Alerts", dot: true },
  { href: "/settings",  icon: Settings,          label: "Settings"  },
];

const CA_NAV = [
  { href: "/ca",         icon: TrendingUp, label: "CA Dashboard" },
  { href: "/ca/clients", icon: Users,      label: "Clients"      },
];

export function Sidebar() {
  const pathname = usePathname();
  const { data: session } = useSession();
  const userType  = (session?.user as any)?.userType;
  const firstName = session?.user?.name?.split(" ")[0] ?? "User";
  const avatar    = session?.user?.image;
  const navItems  = userType === "ca_firm" ? [...NAV, ...CA_NAV] : NAV;

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

  return (
    <aside className="hidden md:flex flex-col w-[240px] min-h-screen bg-[#0A0A0C] border-r border-white/[0.06] flex-shrink-0">
      {/* Logo */}
      <div className="flex items-center gap-3 px-5 h-16 border-b border-white/[0.06]">
        <img src="/logo1.png" alt="Munim" className="w-8 h-8 rounded-xl object-contain" />
        <div>
          <span className="text-white font-bold text-lg tracking-tight">Munim</span>
          <span className="block text-[10px] text-white/30 -mt-0.5 font-medium">AI Business Intelligence</span>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-5 space-y-1 overflow-y-auto scrollbar-thin">
        <p className="section-title px-3 mb-3">Menu</p>
        {navItems.map((item) => {
          const active = pathname === item.href || pathname.startsWith(item.href + "/");
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-150 group",
                active
                  ? "bg-orange-500/15 text-orange-400 border border-orange-500/20"
                  : "text-white/40 hover:text-white/80 hover:bg-white/5"
              )}
            >
              <item.icon className={cn("w-[18px] h-[18px] flex-shrink-0", active ? "text-orange-400" : "")} />
              <span className="flex-1">{item.label}</span>
              {(item as any).dot && !active && !alertsSeen && (
                <span className="w-2 h-2 rounded-full bg-orange-500" />
              )}
              {active && <ChevronRight className="w-3.5 h-3.5 opacity-60" />}
            </Link>
          );
        })}
      </nav>

      {/* User */}
      <div className="px-3 py-4 border-t border-white/[0.06] space-y-1">
        <div className="flex items-center gap-3 px-3 py-2.5 rounded-xl">
          {avatar ? (
            <img src={avatar} className="w-8 h-8 rounded-xl object-cover ring-1 ring-white/10" alt={firstName} />
          ) : (
            <div className="w-8 h-8 rounded-xl bg-orange-500 flex items-center justify-center text-white text-sm font-bold">
              {firstName[0]}
            </div>
          )}
          <div className="flex-1 min-w-0">
            <p className="text-white/90 text-sm font-semibold truncate">{firstName}</p>
            <p className="text-white/30 text-xs truncate">{session?.user?.email}</p>
          </div>
        </div>
        <button
          onClick={() => signOut({ callbackUrl: "/" })}
          className="flex items-center gap-3 w-full px-3 py-2.5 rounded-xl text-white/30 hover:text-white/70 hover:bg-white/5 text-sm font-medium transition-all"
        >
          <LogOut className="w-[18px] h-[18px] flex-shrink-0" />
          Sign out
        </button>
      </div>
    </aside>
  );
}
