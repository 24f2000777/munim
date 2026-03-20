"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, Upload, FileText, Settings } from "lucide-react";
import { cn } from "@/lib/utils";

const TABS = [
  { href: "/dashboard", icon: LayoutDashboard, label: "Home"    },
  { href: "/upload",    icon: Upload,           label: "Upload"  },
  { href: "/reports",   icon: FileText,         label: "Reports" },
  { href: "/settings",  icon: Settings,         label: "More"    },
];

export function MobileNav() {
  const pathname = usePathname();
  return (
    <nav className="md:hidden fixed bottom-0 left-0 right-0 z-40 bg-background/95 backdrop-blur-sm border-t border-border h-16 flex items-center px-2">
      {TABS.map((tab) => {
        const active = pathname === tab.href || pathname.startsWith(tab.href + "/");
        return (
          <Link
            key={tab.href}
            href={tab.href}
            className={cn(
              "flex-1 flex flex-col items-center justify-center gap-1 text-[10px] font-medium transition-colors duration-150 h-full rounded-lg",
              active ? "text-saffron" : "text-muted-foreground"
            )}
          >
            <tab.icon
              className={cn(
                "w-5 h-5 transition-all",
                active ? "stroke-[2.5px]" : "stroke-[1.8px]"
              )}
            />
            {tab.label}
          </Link>
        );
      })}
    </nav>
  );
}
