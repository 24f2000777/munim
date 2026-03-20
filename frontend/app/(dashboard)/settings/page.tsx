"use client";
import { useSession } from "next-auth/react";
import { useState, useEffect } from "react";
import { useUserProfile, useUpdateProfile } from "@/lib/api/user";
import { toast } from "sonner";
import { Save, Loader2, MessageCircle, Globe, Phone } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Language } from "@/lib/types";

const LANGUAGES: { key: Language; label: string }[] = [
  { key: "hi",       label: "Hindi"    },
  { key: "en",       label: "English"  },
  { key: "hinglish", label: "Hinglish" },
];

export default function SettingsPage() {
  const { data: session } = useSession();
  const { data: profile } = useUserProfile();

  const [phone,    setPhone]    = useState("");
  const [language, setLanguage] = useState<Language>("hi");
  const [waOptIn,  setWaOptIn]  = useState(false);
  const [dirty,    setDirty]    = useState(false);

  useEffect(() => {
    if (profile) {
      setPhone(profile.phone ?? "");
      setLanguage(profile.language_preference);
      setWaOptIn(profile.whatsapp_opted_in);
    }
  }, [profile]);

  const updateMutation = useUpdateProfile();

  const handleSave = async () => {
    try {
      await updateMutation.mutateAsync({
        language_preference: language,
        phone:               phone || undefined,
        whatsapp_opted_in:   waOptIn,
      });
      toast.success("Settings saved");
      setDirty(false);
    } catch (e: any) {
      toast.error(e.message ?? "Save failed");
    }
  };

  const mark = () => setDirty(true);

  return (
    <div className="max-w-5xl mx-auto animate-fade-in">
      <div className="mb-6">
        <h1 className="text-xl font-bold text-forest">Settings</h1>
        <p className="text-sm text-muted-foreground mt-0.5">Manage your account and preferences</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {/* Left column */}
        <div className="md:col-span-2 space-y-4">
          {/* Profile */}
          <div className="bg-card border border-border rounded-2xl p-5 shadow-metric">
            <h2 className="font-semibold text-forest text-sm mb-4">Profile</h2>
            <div className="flex items-center gap-4 mb-5">
              {session?.user?.image ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={session.user.image}
                  alt="avatar"
                  className="w-12 h-12 rounded-2xl border-2 border-saffron/20 object-cover"
                />
              ) : (
                <div className="w-12 h-12 rounded-2xl bg-saffron/10 flex items-center justify-center text-saffron text-lg font-bold">
                  {session?.user?.name?.slice(0, 1)}
                </div>
              )}
              <div>
                <p className="font-bold text-forest">{session?.user?.name}</p>
                <p className="text-xs text-muted-foreground">{session?.user?.email}</p>
                <span className="text-xs font-semibold text-saffron bg-saffron/10 px-2 py-0.5 rounded-full mt-1 inline-block capitalize">
                  {profile?.user_type?.replace("_", " ") ?? "Loading..."}
                </span>
              </div>
            </div>

            <div>
              <label className="flex items-center gap-1.5 text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1.5">
                <Phone className="w-3 h-3" /> WhatsApp Phone Number
              </label>
              <div className="flex items-center border border-border rounded-xl overflow-hidden focus-within:ring-2 focus-within:ring-saffron/30">
                <span className="px-3 py-2.5 bg-muted text-sm font-semibold text-muted-foreground border-r border-border">+91</span>
                <input
                  type="tel"
                  value={phone.replace(/^\+91/, "")}
                  onChange={(e) => { setPhone(e.target.value); mark(); }}
                  placeholder="9876543210"
                  className="flex-1 px-3 py-2.5 text-sm text-forest bg-card focus:outline-none"
                />
              </div>
            </div>
          </div>

          {/* Language */}
          <div className="bg-card border border-border rounded-2xl p-5 shadow-metric">
            <div className="flex items-center gap-2 mb-4">
              <Globe className="w-4 h-4 text-muted-foreground" />
              <h2 className="font-semibold text-forest text-sm">Report Language</h2>
            </div>
            <div className="grid grid-cols-3 gap-2">
              {LANGUAGES.map((lang) => (
                <button
                  key={lang.key}
                  onClick={() => { setLanguage(lang.key); mark(); }}
                  className={cn(
                    "py-2.5 rounded-xl border text-sm font-semibold transition-all",
                    language === lang.key
                      ? "bg-saffron/10 border-saffron/30 text-saffron"
                      : "border-border text-muted-foreground hover:border-saffron/20",
                  )}
                >
                  {lang.label}
                </button>
              ))}
            </div>
            <p className="text-xs text-muted-foreground mt-2.5">
              Your WhatsApp reports will be generated in this language.
            </p>
          </div>
        </div>

        {/* Right column */}
        <div className="space-y-4">
          {/* WhatsApp */}
          <div className="bg-card border border-border rounded-2xl p-5 shadow-metric">
            <div className="flex items-start justify-between gap-3 mb-3">
              <div className="flex items-start gap-3">
                <div className="w-8 h-8 rounded-xl bg-green-100 flex items-center justify-center flex-shrink-0">
                  <MessageCircle className="w-4 h-4 text-green-600" />
                </div>
                <div>
                  <p className="font-semibold text-forest text-sm">WhatsApp Reports</p>
                  <p className="text-xs text-muted-foreground mt-0.5">Every Monday at 8 AM</p>
                </div>
              </div>
              <button
                onClick={() => { setWaOptIn((v) => !v); mark(); }}
                className={cn(
                  "relative w-11 h-6 rounded-full transition-all duration-300 flex-shrink-0 mt-0.5",
                  waOptIn ? "bg-green-500" : "bg-border",
                )}
              >
                <span className={cn(
                  "absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow-sm transition-all duration-300",
                  waOptIn ? "translate-x-5" : "translate-x-0",
                )} />
              </button>
            </div>
            {waOptIn && !phone && (
              <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
                Add your phone number to receive WhatsApp reports.
              </p>
            )}
          </div>

          {/* Save */}
          <button
            onClick={handleSave}
            disabled={!dirty || updateMutation.isPending}
            className={cn(
              "w-full flex items-center justify-center gap-2 py-2.5 rounded-xl font-semibold text-sm transition-all",
              dirty
                ? "bg-saffron hover:bg-saffron-dark text-white shadow-warm"
                : "bg-muted text-muted-foreground cursor-not-allowed",
            )}
          >
            {updateMutation.isPending ? (
              <><Loader2 className="w-4 h-4 animate-spin" /> Saving...</>
            ) : (
              <><Save className="w-4 h-4" /> Save Changes</>
            )}
          </button>

          <div className="bg-muted/50 border border-border rounded-2xl p-4">
            <p className="text-xs font-semibold text-muted-foreground mb-1">Account type</p>
            <p className="text-sm font-semibold text-forest capitalize">
              {profile?.user_type?.replace("_", " ") ?? "Loading..."}
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              Member since {profile ? new Date(profile.created_at).getFullYear() : "—"}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
