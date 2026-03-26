"use client";
import { signIn } from "next-auth/react";
import { useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { Loader2, TrendingUp, BarChart3, MessageSquare, CheckCircle2 } from "lucide-react";

function LoginForm() {
  const [loading, setLoading] = useState(false);
  const searchParams = useSearchParams();
  const callbackUrl = searchParams.get("callbackUrl") ?? "/dashboard";

  async function handleGoogle() {
    setLoading(true);
    await signIn("google", { callbackUrl });
  }

  return (
    <div className="min-h-screen bg-[#0D0D0F] flex">
      {/* Left: Brand panel */}
      <div className="hidden lg:flex flex-col justify-between w-[480px] bg-[#0A0A0C] border-r border-white/[0.06] p-10 flex-shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-orange-500 rounded-2xl flex items-center justify-center shadow-lg shadow-orange-500/30">
            <span className="text-white font-bold text-base">म</span>
          </div>
          <div>
            <span className="text-white font-bold text-xl">Munim</span>
            <span className="block text-white/30 text-xs">AI Business Intelligence</span>
          </div>
        </div>

        <div>
          <h2 className="text-4xl font-bold text-white leading-tight mb-4">
            Your AI-powered<br />business accountant.
          </h2>
          <p className="text-white/40 text-base leading-relaxed mb-10">
            Upload sales data from Tally, Excel, or CSV. Get instant AI analysis, anomaly detection, and WhatsApp reports.
          </p>

          <div className="space-y-5">
            {[
              { icon: TrendingUp,   title: "Revenue analytics",     desc: "Track trends, spot patterns instantly" },
              { icon: BarChart3,    title: "AI anomaly detection",   desc: "Never miss what matters in your data" },
              { icon: MessageSquare,title: "WhatsApp reports",       desc: "In Hindi, English or Hinglish"        },
            ].map((f) => (
              <div key={f.title} className="flex items-center gap-4">
                <div className="w-10 h-10 rounded-2xl bg-orange-500/10 border border-orange-500/20 flex items-center justify-center flex-shrink-0">
                  <f.icon className="w-5 h-5 text-orange-400" />
                </div>
                <div>
                  <p className="text-white/90 text-base font-semibold">{f.title}</p>
                  <p className="text-white/35 text-sm">{f.desc}</p>
                </div>
              </div>
            ))}
          </div>

          <div className="mt-10 p-4 rounded-2xl bg-white/[0.03] border border-white/[0.06]">
            <div className="flex items-center gap-2 mb-2">
              <CheckCircle2 className="w-4 h-4 text-orange-400" />
              <span className="text-white/60 text-sm font-medium">Analysis complete in 17 seconds</span>
            </div>
            <div className="grid grid-cols-3 gap-3">
              {[
                { v: "₹2,45,000", l: "Revenue" },
                { v: "6",         l: "Customers" },
                { v: "2",         l: "Alerts" },
              ].map((s) => (
                <div key={s.l} className="bg-white/[0.04] rounded-xl p-3 text-center">
                  <p className="text-white font-bold text-lg">{s.v}</p>
                  <p className="text-white/30 text-xs">{s.l}</p>
                </div>
              ))}
            </div>
          </div>
        </div>

        <p className="text-white/20 text-sm">Built for Indian businesses</p>
      </div>

      {/* Right: Login form */}
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="w-full max-w-sm">
          <div className="flex items-center gap-3 mb-12 lg:hidden">
            <div className="w-10 h-10 bg-orange-500 rounded-2xl flex items-center justify-center shadow-lg shadow-orange-500/30">
              <span className="text-white font-bold text-base">म</span>
            </div>
            <span className="text-white font-bold text-xl">Munim</span>
          </div>

          <div className="mb-10">
            <h1 className="text-4xl font-bold text-foreground tracking-tight mb-3">Welcome back</h1>
            <p className="text-base text-muted-foreground">Sign in to access your dashboard</p>
          </div>

          <button
            onClick={handleGoogle}
            disabled={loading}
            className="w-full flex items-center justify-center gap-3 bg-secondary hover:bg-secondary/70 border border-border text-foreground font-semibold text-base px-5 py-4 rounded-2xl transition-all duration-150 disabled:opacity-60 hover:border-orange-500/30"
          >
            {loading ? (
              <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
            ) : (
              <svg className="w-5 h-5" viewBox="0 0 24 24">
                <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
                <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
                <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
                <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
              </svg>
            )}
            {loading ? "Signing in..." : "Continue with Google"}
          </button>

          <p className="text-center text-sm text-muted-foreground mt-8 leading-relaxed">
            By signing in, you agree to our<br />terms of service and privacy policy.
          </p>
        </div>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}
