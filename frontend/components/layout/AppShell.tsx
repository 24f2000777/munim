"use client";
import { useState } from "react";
import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";
import { MobileNav } from "./MobileNav";

// Simple Sheet-like mobile drawer without @radix-ui/react-sheet
function MobileDrawer({
  open,
  onClose,
  children,
}: {
  open:     boolean;
  onClose:  () => void;
  children: React.ReactNode;
}) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 md:hidden">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/40 backdrop-blur-sm"
        onClick={onClose}
      />
      {/* Drawer */}
      <div className="absolute left-0 top-0 bottom-0 w-64 animate-slide-up">
        {children}
      </div>
    </div>
  );
}

interface AppShellProps {
  children: React.ReactNode;
  userType?: string;
}

export function AppShell({ children, userType = "smb_owner" }: AppShellProps) {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      {/* Desktop sidebar */}
      <div className="hidden md:flex flex-shrink-0">
        <Sidebar userType={userType} />
      </div>

      {/* Mobile drawer */}
      <MobileDrawer open={mobileOpen} onClose={() => setMobileOpen(false)}>
        <Sidebar userType={userType} />
      </MobileDrawer>

      {/* Main */}
      <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
        <TopBar onMenuToggle={() => setMobileOpen(true)} />
        <main className="flex-1 overflow-y-auto">
          <div className="max-w-6xl mx-auto px-4 md:px-6 py-6 pb-24 md:pb-8">
            {children}
          </div>
        </main>
        <MobileNav />
      </div>
    </div>
  );
}
