"use client";

import Link from "next/link";
import { useState } from "react";
import { ArrowRight, BarChart3, Zap, MessageSquare, TrendingUp, Users, Shield, CheckCircle2, Loader2 } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function HomePage() {
  const [phone, setPhone] = useState("");
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(false);
  const [joined, setJoined] = useState(false);
  const [alreadyJoined, setAlreadyJoined] = useState(false);
  const [waLink, setWaLink] = useState("");
  const [error, setError] = useState("");
  const [slowWarn, setSlowWarn] = useState(false);

  async function handleJoin(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    const cleaned = phone.replace(/[\s\-()]/g, "");
    // If user entered with country code, strip it for validation
    const digitsOnly = cleaned.replace(/^\+?91/, "");
    if (!digitsOnly || digitsOnly.length !== 10 || !/^\d{10}$/.test(digitsOnly)) {
      setError("Please enter a valid 10-digit Indian mobile number");
      return;
    }
    const fullPhone = `+91${digitsOnly}`;
    setLoading(true);
    setSlowWarn(false);
    const slowTimer = setTimeout(() => setSlowWarn(true), 8000);
    try {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 60000);
      const res = await fetch(`${API_BASE}/api/v1/beta/join`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phone: fullPhone, name }),
        signal: controller.signal,
      });
      clearTimeout(timeout);
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Something went wrong");
      setAlreadyJoined(data.already_joined === true);
      setWaLink(data.whatsapp_link || "");
      setJoined(true);
    } catch (err: any) {
      if (err.name === "AbortError") {
        setError("Server is waking up — please try again in 30 seconds.");
      } else {
        setError(err.message || "Could not join. Please try again.");
      }
    } finally {
      clearTimeout(slowTimer);
      setLoading(false);
      setSlowWarn(false);
    }
  }

  return (
    <div className="min-h-screen bg-[#0D0D0F] text-white">
      {/* Nav */}
      <nav className="fixed top-0 inset-x-0 z-50 bg-[#0D0D0F]/80 backdrop-blur-xl border-b border-white/[0.06]">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <img src="/logo1.png" alt="Munim" className="w-8 h-8 rounded-xl object-contain" />
            <span className="font-bold text-white text-lg">Munim</span>
          </div>
          <Link href="/login"
            className="inline-flex items-center gap-2 bg-orange-500 hover:bg-orange-600 text-white text-sm font-semibold px-5 py-2.5 rounded-xl transition-colors shadow-lg shadow-orange-500/20">
            Sign in <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      </nav>

      {/* Hero */}
      <section className="pt-36 pb-24 px-6">
        <div className="max-w-5xl mx-auto text-center">
          <div className="inline-flex items-center gap-2 bg-orange-500/10 border border-orange-500/20 text-orange-400 text-sm font-semibold px-4 py-2 rounded-full mb-8">
            <Zap className="w-3.5 h-3.5" />
            AI-powered business intelligence for India
          </div>
          <h1 className="text-6xl md:text-7xl font-bold text-white tracking-tight leading-[1.05] mb-8">
            Know your business.<br />
            <span style={{ background: "linear-gradient(135deg, #F97316, #FB923C)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
              Instantly.
            </span>
          </h1>
          <p className="text-xl text-white/50 max-w-2xl mx-auto mb-12 leading-relaxed">
            Send your sales file on WhatsApp. Munim analyzes everything in 60 seconds — revenue trends, customer insights, anomalies — no app, no login needed.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <a href="#join"
              className="inline-flex items-center justify-center gap-2 bg-orange-500 hover:bg-orange-600 text-white font-bold text-lg px-8 py-4 rounded-2xl transition-all shadow-xl shadow-orange-500/25 hover:shadow-orange-500/40">
              Join Beta on WhatsApp <ArrowRight className="w-5 h-5" />
            </a>
            <a href="#features"
              className="inline-flex items-center justify-center gap-2 bg-white/5 hover:bg-white/10 border border-white/10 text-white font-semibold text-lg px-8 py-4 rounded-2xl transition-all">
              See how it works
            </a>
          </div>
        </div>

        {/* Dashboard preview */}
        <div className="max-w-4xl mx-auto mt-20">
          <div className="rounded-3xl border border-white/10 overflow-hidden bg-[#161618] shadow-2xl">
            <div className="bg-[#0A0A0C] px-5 py-3 flex items-center gap-3 border-b border-white/[0.06]">
              <div className="flex gap-1.5">
                <div className="w-3 h-3 rounded-full bg-red-500/70" />
                <div className="w-3 h-3 rounded-full bg-yellow-500/70" />
                <div className="w-3 h-3 rounded-full bg-green-500/70" />
              </div>
              <span className="text-white/20 text-sm mx-auto font-mono">munim.app/dashboard</span>
            </div>
            <div className="p-6">
              <p className="text-white/40 text-sm mb-4 font-medium">Good morning, Rahul 👋</p>
              <div className="grid grid-cols-4 gap-3 mb-4">
                {[
                  { l: "Revenue",      v: "₹2,45,000", c: "+12%",  color: "from-orange-500/20 to-orange-500/5 border-orange-500/20" },
                  { l: "Transactions", v: "1,247",      c: "+8%",   color: "from-emerald-500/20 to-emerald-500/5 border-emerald-500/20" },
                  { l: "Customers",    v: "89",         c: "+3",    color: "from-blue-500/20 to-blue-500/5 border-blue-500/20" },
                  { l: "Health",       v: "94/100",     c: "Excellent", color: "from-purple-500/20 to-purple-500/5 border-purple-500/20" },
                ].map((m) => (
                  <div key={m.l} className={`rounded-2xl border p-4 bg-gradient-to-br ${m.color}`}>
                    <p className="text-white/40 text-xs mb-2">{m.l}</p>
                    <p className="text-white font-bold text-xl mb-1">{m.v}</p>
                    <p className="text-emerald-400 text-xs font-semibold">{m.c}</p>
                  </div>
                ))}
              </div>
              <div className="rounded-2xl bg-white/[0.03] border border-white/[0.06] p-4 h-24 flex items-center justify-center">
                <p className="text-white/20 text-sm">Revenue chart</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="py-24 px-6 bg-[#0A0A0C] border-y border-white/[0.06]">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-16">
            <p className="text-orange-400 text-sm font-bold uppercase tracking-widest mb-4">Why Munim</p>
            <h2 className="text-4xl font-bold text-white tracking-tight">Everything your business needs</h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            {[
              { icon: Zap,           title: "Instant Analysis",      desc: "Send any format on WhatsApp — Tally XML, Excel, or CSV. Get full AI analysis in under 60 seconds.", color: "bg-orange-500/15 text-orange-400 border-orange-500/20" },
              { icon: TrendingUp,    title: "Smart Insights",        desc: "AI detects anomalies, segments customers, spots dead stock, and surfaces actionable intelligence.", color: "bg-emerald-500/15 text-emerald-400 border-emerald-500/20" },
              { icon: MessageSquare, title: "WhatsApp First",        desc: "No app to download. No login required. Just send your file on WhatsApp and get your report instantly.", color: "bg-blue-500/15 text-blue-400 border-blue-500/20" },
              { icon: Shield,        title: "Data Privacy",          desc: "Your business data is encrypted, processed securely, and never shared with third parties.", color: "bg-purple-500/15 text-purple-400 border-purple-500/20" },
              { icon: BarChart3,     title: "Revenue Analytics",     desc: "Track revenue trends week over week, identify top products, and understand seasonality.", color: "bg-pink-500/15 text-pink-400 border-pink-500/20" },
              { icon: Users,         title: "Customer Segmentation", desc: "RFM analysis groups your customers by loyalty — focus on the right people at the right time.", color: "bg-yellow-500/15 text-yellow-400 border-yellow-500/20" },
            ].map((f) => (
              <div key={f.title} className="bg-[#161618] border border-white/[0.07] rounded-3xl p-7 hover:border-orange-500/20 transition-colors duration-200">
                <div className={`w-12 h-12 rounded-2xl border flex items-center justify-center mb-5 ${f.color}`}>
                  <f.icon className="w-5 h-5" />
                </div>
                <h3 className="text-lg font-bold text-white mb-3">{f.title}</h3>
                <p className="text-base text-white/40 leading-relaxed">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* How it works */}
      <section className="py-24 px-6">
        <div className="max-w-4xl mx-auto text-center">
          <p className="text-orange-400 text-sm font-bold uppercase tracking-widest mb-4">How it works</p>
          <h2 className="text-4xl font-bold text-white tracking-tight mb-16">3 steps. 60 seconds.</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {[
              { step: "1", title: "Join beta", desc: "Enter your WhatsApp number below. We'll send you a welcome message instantly.", emoji: "👇" },
              { step: "2", title: "Send your file", desc: "Reply with your sales file — CSV, Excel, Tally XML, or even a photo of your register.", emoji: "📁" },
              { step: "3", title: "Get your analysis", desc: "Full business report in 60 seconds. Revenue, top products, alerts, customer insights.", emoji: "📊" },
            ].map((s) => (
              <div key={s.step} className="flex flex-col items-center">
                <div className="w-14 h-14 rounded-2xl bg-orange-500/10 border border-orange-500/20 flex items-center justify-center text-2xl mb-5">
                  {s.emoji}
                </div>
                <div className="text-orange-400 text-xs font-bold uppercase tracking-widest mb-2">Step {s.step}</div>
                <h3 className="text-lg font-bold text-white mb-2">{s.title}</h3>
                <p className="text-white/40 text-sm leading-relaxed">{s.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Beta Join Form */}
      <section id="join" className="py-24 px-6 bg-[#0A0A0C] border-t border-white/[0.06]">
        <div className="max-w-lg mx-auto text-center">
          <div className="inline-flex items-center gap-2 bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-sm font-semibold px-4 py-2 rounded-full mb-8">
            <MessageSquare className="w-3.5 h-3.5" />
            Private Beta — Limited Spots
          </div>
          <h2 className="text-4xl font-bold text-white tracking-tight mb-4">
            Start on WhatsApp.<br />Right now.
          </h2>
          <p className="text-white/40 text-base mb-10 leading-relaxed">
            Enter your WhatsApp number to join the beta — then open WhatsApp and send your sales file to get your first analysis in 60 seconds.
          </p>

          {joined ? (
            /* Success state */
            <div className="bg-emerald-500/10 border border-emerald-500/20 rounded-3xl p-10 flex flex-col items-center gap-5">
              <CheckCircle2 className="w-14 h-14 text-emerald-400" />
              <h3 className="text-2xl font-bold text-white">
                {alreadyJoined ? "Welcome back! 👋" : "You're in! 🎉"}
              </h3>
              <p className="text-white/50 text-base leading-relaxed text-center">
                {alreadyJoined
                  ? "You're already on the beta. Click below to open WhatsApp and chat with Munim."
                  : "You're registered! Now open WhatsApp, say Hi, and send your sales file to get started."
                }
              </p>
              {waLink ? (
                <a
                  href={waLink}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="w-full inline-flex items-center justify-center gap-2 bg-[#25D366] hover:bg-[#1ebe5d] text-white font-bold text-lg px-6 py-4 rounded-2xl transition-all shadow-lg shadow-green-500/20 mt-1"
                >
                  <MessageSquare className="w-5 h-5" />
                  Open WhatsApp &amp; Start Now →
                </a>
              ) : null}
              <p className="text-white/30 text-xs text-center">
                Send "Hi" to start • Then upload your sales CSV/Excel file • Get analysis in 60 sec
              </p>
            </div>
          ) : (
            /* Join form */
            <form onSubmit={handleJoin} className="bg-[#161618] border border-white/[0.07] rounded-3xl p-8 text-left">
              <div className="mb-5">
                <label className="block text-sm font-semibold text-white/60 mb-2">Your name (optional)</label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Rahul Sharma"
                  className="w-full bg-white/[0.04] border border-white/10 rounded-xl px-4 py-3 text-white placeholder:text-white/20 focus:outline-none focus:border-orange-500/50 transition-colors text-base"
                />
              </div>
              <div className="mb-6">
                <label className="block text-sm font-semibold text-white/60 mb-2">WhatsApp number *</label>
                <div className="flex">
                  <span className="px-4 py-3 bg-white/[0.04] border border-white/10 border-r-0 rounded-l-xl text-white/40 font-semibold text-base select-none">
                    +91
                  </span>
                  <input
                    type="tel"
                    value={phone}
                    onChange={(e) => {
                      // Only allow digits and spaces
                      const val = e.target.value.replace(/[^\d\s]/g, "");
                      setPhone(val);
                    }}
                    placeholder="98765 43210"
                    maxLength={14}
                    required
                    className="flex-1 bg-white/[0.04] border border-white/10 rounded-r-xl px-4 py-3 text-white placeholder:text-white/20 focus:outline-none focus:border-orange-500/50 transition-colors text-base"
                  />
                </div>
                {error && <p className="text-red-400 text-sm mt-2">{error}</p>}
              </div>
              <button
                type="submit"
                disabled={loading}
                className="w-full inline-flex items-center justify-center gap-2 bg-orange-500 hover:bg-orange-600 disabled:opacity-60 disabled:cursor-not-allowed text-white font-bold text-lg px-8 py-4 rounded-2xl transition-all shadow-xl shadow-orange-500/25">
                {loading ? (
                  <><Loader2 className="w-5 h-5 animate-spin" /> {slowWarn ? "Waking server up..." : "Joining..."}</>
                ) : (
                  <>Join Beta — Get WhatsApp Access <ArrowRight className="w-5 h-5" /></>
                )}
              </button>
              <p className="text-white/20 text-xs text-center mt-4">
                We'll send one WhatsApp message. No spam, ever.
              </p>
            </form>
          )}
        </div>
      </section>

      {/* Stats */}
      <section className="py-20 px-6">
        <div className="max-w-4xl mx-auto">
          <div className="grid grid-cols-3 gap-6 text-center">
            {[
              { value: "60s",   label: "Average analysis time" },
              { value: "Any",   label: "File format supported" },
              { value: "100%",  label: "Powered by AI" },
            ].map((s) => (
              <div key={s.label} className="bg-[#161618] border border-white/[0.07] rounded-3xl p-8">
                <p className="text-5xl font-bold text-white mb-2">{s.value}</p>
                <p className="text-base text-white/40">{s.label}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Footer CTA */}
      <section className="py-24 px-6 bg-[#0A0A0C] border-t border-white/[0.06]">
        <div className="max-w-2xl mx-auto text-center">
          <h2 className="text-4xl font-bold text-white tracking-tight mb-4">
            Already have an account?
          </h2>
          <p className="text-lg text-white/40 mb-10">Access the full dashboard with charts and detailed reports.</p>
          <Link href="/login"
            className="inline-flex items-center gap-2 bg-orange-500 hover:bg-orange-600 text-white font-bold text-xl px-10 py-5 rounded-2xl transition-all shadow-2xl shadow-orange-500/25 hover:shadow-orange-500/40">
            Sign in with Google <ArrowRight className="w-5 h-5" />
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-white/[0.06] px-6 py-8">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-6 h-6 bg-orange-500 rounded-lg flex items-center justify-center">
              <span className="text-white text-[10px] font-bold">म</span>
            </div>
            <span className="text-white/30 text-sm">Munim — Your digital accountant</span>
          </div>
          <p className="text-white/20 text-sm">Built for Indian businesses</p>
        </div>
      </footer>
    </div>
  );
}
