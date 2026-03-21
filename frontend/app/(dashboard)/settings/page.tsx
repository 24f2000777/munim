"use client";
import { useState, useEffect } from "react";
import { useSession } from "next-auth/react";
import { Save, MessageSquare, User, Globe, Bell } from "lucide-react";
import { toast } from "sonner";
import { useUserProfile, useUpdateProfile } from "@/lib/api/user";
import type { Language } from "@/lib/types";

const LANGUAGES = [
  { value: "en",       label: "English",  desc: "Reports in English"       },
  { value: "hi",       label: "Hindi",    desc: "रिपोर्ट हिंदी में"          },
  { value: "hinglish", label: "Hinglish", desc: "Mix of Hindi and English" },
];

function Toggle({ on, onToggle }: { on: boolean; onToggle: () => void }) {
  return (
    <button
      onClick={onToggle}
      className={`relative w-12 h-6 rounded-full transition-colors duration-200 ${
        on ? "bg-orange-500" : "bg-secondary border border-border"
      }`}
    >
      <span
        className={`absolute top-1 left-1 w-4 h-4 bg-white rounded-full shadow transition-transform duration-200 ${
          on ? "translate-x-6" : ""
        }`}
      />
    </button>
  );
}

function loadNotifPref(key: string, fallback: boolean): boolean {
  if (typeof window === "undefined") return fallback;
  const v = localStorage.getItem(key);
  return v === null ? fallback : v === "true";
}

export default function SettingsPage() {
  const { data: session } = useSession();
  const { data: profile, isLoading: profileLoading } = useUserProfile();
  const updateProfile = useUpdateProfile();

  const [language, setLanguage] = useState<Language>("en");
  const [whatsapp, setWhatsapp] = useState(false);
  const [phone,    setPhone]    = useState("");

  // Notification toggles — persisted in localStorage
  const [notifAnalysis, setNotifAnalysis] = useState(true);
  const [notifAlerts,   setNotifAlerts]   = useState(true);
  const [notifWeekly,   setNotifWeekly]   = useState(false);

  // Load notification prefs from localStorage on mount
  useEffect(() => {
    setNotifAnalysis(loadNotifPref("notif_analysis", true));
    setNotifAlerts(loadNotifPref("notif_alerts", true));
    setNotifWeekly(loadNotifPref("notif_weekly", false));
  }, []);

  // Populate form from real profile data once loaded
  useEffect(() => {
    if (profile) {
      setLanguage(profile.language_preference ?? "en");
      setWhatsapp(profile.whatsapp_opted_in ?? false);
      // Strip +91 prefix for display in the input
      setPhone((profile.phone ?? "").replace(/^\+91/, ""));
    }
  }, [profile]);

  const name   = session?.user?.name  ?? "";
  const email  = session?.user?.email ?? "";
  const avatar = session?.user?.image;
  const saving = updateProfile.isPending;

  async function handleSave() {
    try {
      await updateProfile.mutateAsync({
        language_preference: language,
        phone:               whatsapp && phone.trim() ? `+91${phone.replace(/\D/g, "")}` : undefined,
        whatsapp_opted_in:   whatsapp,
      });
      toast.success("Settings saved successfully");
    } catch {
      toast.error("Failed to save settings. Please try again.");
    }
  }

  return (
    <div className="p-6 animate-fade-in max-w-2xl space-y-4">
      <div className="mb-6">
        <h1 className="page-title">Settings</h1>
        <p className="page-subtitle">Manage your account preferences</p>
      </div>

      {/* Profile — read-only from Google OAuth */}
      <div className="card p-6">
        <div className="flex items-center gap-2 mb-5">
          <User className="w-5 h-5 text-muted-foreground" />
          <h2 className="text-lg font-bold text-foreground">Profile</h2>
        </div>
        <div className="flex items-center gap-5">
          {avatar ? (
            <img src={avatar} className="w-16 h-16 rounded-2xl object-cover" alt={name} />
          ) : (
            <div className="w-16 h-16 rounded-2xl bg-orange-500 flex items-center justify-center text-white font-bold text-2xl">
              {name[0]}
            </div>
          )}
          <div>
            <p className="text-xl font-bold text-foreground">{name}</p>
            <p className="text-base text-muted-foreground mt-0.5">{email}</p>
            <span className="badge badge-neutral text-sm mt-2">Google account</span>
          </div>
        </div>
      </div>

      {/* Language preference */}
      <div className="card p-6">
        <div className="flex items-center gap-2 mb-5">
          <Globe className="w-5 h-5 text-muted-foreground" />
          <h2 className="text-lg font-bold text-foreground">Report language</h2>
        </div>
        <div className="grid grid-cols-3 gap-3">
          {LANGUAGES.map((l) => (
            <button
              key={l.value}
              onClick={() => setLanguage(l.value as Language)}
              className={`p-4 rounded-2xl border text-left transition-all duration-150 ${
                language === l.value
                  ? "border-orange-500 bg-orange-500/10"
                  : "border-border hover:border-orange-500/30 hover:bg-secondary/50"
              }`}
            >
              <p className={`font-bold text-base mb-1 ${language === l.value ? "text-orange-400" : "text-foreground"}`}>
                {l.label}
              </p>
              <p className="text-sm text-muted-foreground">{l.desc}</p>
            </button>
          ))}
        </div>
      </div>

      {/* WhatsApp reports */}
      <div className="card p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <MessageSquare className="w-5 h-5 text-muted-foreground" />
            <h2 className="text-lg font-bold text-foreground">WhatsApp reports</h2>
          </div>
          <Toggle on={whatsapp} onToggle={() => setWhatsapp((v) => !v)} />
        </div>
        {whatsapp && (
          <div className="mt-2">
            <label className="text-sm font-semibold text-muted-foreground mb-2 block">
              Phone number
            </label>
            <div className="flex">
              <span className="px-4 py-2.5 bg-secondary border border-border border-r-0 rounded-l-xl text-base text-muted-foreground font-semibold">
                +91
              </span>
              <input
                type="tel"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="98765 43210"
                className="input-field rounded-l-none flex-1"
              />
            </div>
            <p className="text-sm text-muted-foreground mt-2">
              Reports will be sent after each analysis completes.
            </p>
          </div>
        )}
      </div>

      {/* Notifications — persisted in localStorage */}
      <div className="card p-6">
        <div className="flex items-center gap-2 mb-5">
          <Bell className="w-5 h-5 text-muted-foreground" />
          <h2 className="text-lg font-bold text-foreground">Notifications</h2>
        </div>
        <div className="space-y-4">
          {[
            {
              label: "Analysis complete",
              desc:  "When file processing finishes",
              on:    notifAnalysis,
              toggle: () => {
                const next = !notifAnalysis;
                setNotifAnalysis(next);
                localStorage.setItem("notif_analysis", String(next));
              },
            },
            {
              label: "High severity alerts",
              desc:  "Critical anomalies detected",
              on:    notifAlerts,
              toggle: () => {
                const next = !notifAlerts;
                setNotifAlerts(next);
                localStorage.setItem("notif_alerts", String(next));
              },
            },
            {
              label: "Weekly summary",
              desc:  "Summary every Monday morning",
              on:    notifWeekly,
              toggle: () => {
                const next = !notifWeekly;
                setNotifWeekly(next);
                localStorage.setItem("notif_weekly", String(next));
              },
            },
          ].map((n, i) => (
            <div
              key={n.label}
              className={`flex items-center justify-between py-4 ${i < 2 ? "border-b border-border" : ""}`}
            >
              <div>
                <p className="text-base font-semibold text-foreground">{n.label}</p>
                <p className="text-sm text-muted-foreground mt-0.5">{n.desc}</p>
              </div>
              <Toggle on={n.on} onToggle={n.toggle} />
            </div>
          ))}
        </div>
      </div>

      <button
        onClick={handleSave}
        disabled={saving || profileLoading}
        className="btn-primary w-full justify-center py-3 text-base"
      >
        {saving ? (
          <>
            <span className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            Saving...
          </>
        ) : (
          <>
            <Save className="w-5 h-5" />
            Save settings
          </>
        )}
      </button>
    </div>
  );
}
