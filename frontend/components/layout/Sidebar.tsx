"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard, Upload, FileText, Bell, Settings,
  BarChart3, Users, BookOpen,
} from "lucide-react";
import { cn } from "@/lib/utils";

type NavItem = {
  href:    string;
  label:   string;
  labelHi: string;
  icon:    React.ElementType;
  caOnly?: boolean;
};

const NAV_ITEMS: NavItem[] = [
  { href: "/dashboard", label: "Dashboard", labelHi: "डैशबोर्ड", icon: LayoutDashboard },
  { href: "/upload",    label: "Upload",    labelHi: "अपलोड",     icon: Upload           },
  { href: "/reports",   label: "Reports",   labelHi: "रिपोर्ट",   icon: FileText         },
  { href: "/alerts",    label: "Alerts",    labelHi: "अलर्ट",     icon: Bell             },
  { href: "/settings",  label: "Settings",  labelHi: "सेटिंग",    icon: Settings         },
  { href: "/ca",        label: "CA Portal", labelHi: "CA पोर्टल", icon: BarChart3, caOnly: true },
  { href: "/clients",   label: "Clients",   labelHi: "क्लाइंट",   icon: Users,    caOnly: true },
];

interface SidebarProps {
  userType?: string;
}

export function Sidebar({ userType = "smb_owner" }: SidebarProps) {
  const pathname = usePathname();
  const isCA     = userType === "ca_firm";
  const items    = NAV_ITEMS.filter((i) => !i.caOnly || isCA);

  return (
    <aside className="flex flex-col h-full w-64 bg-forest text-cream">
      {/* Brand */}
      <div className="flex items-center gap-3 px-5 py-5 border-b border-white/10">
        <div className="w-9 h-9 rounded-xl bg-saffron flex items-center justify-center font-bold text-white text-base shadow-warm">
          म
        </div>
        <div>
          <p className="text-base font-bold text-cream tracking-tight leading-none">Munim</p>
          <p className="text-[10px] text-cream/50 font-medium mt-0.5 hindi">मुनीम</p>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
        {items.map((item) => {
          const active =
            pathname === item.href ||
            (item.href !== "/" && pathname.startsWith(item.href));
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "nav-link",
                active ? "nav-link-active" : "nav-link-default"
              )}
            >
              <item.icon className="w-[18px] h-[18px] flex-shrink-0" />
              <span className="truncate">{item.label}</span>
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="px-4 pb-5 pt-3 border-t border-white/10">
        {isCA ? (
          <div className="flex items-center gap-2">
            <BookOpen className="w-4 h-4 text-golden" />
            <span className="text-xs font-semibold text-golden">CA Firm Account</span>
          </div>
        ) : (
          <p className="text-[11px] text-cream/40 font-medium">
            Your digital Munim
          </p>
        )}
      </div>
    </aside>
  );
}
