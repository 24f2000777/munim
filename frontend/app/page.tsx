import Link from "next/link";
import { ArrowRight, BarChart3, Zap, MessageSquare, TrendingUp, Users, Shield } from "lucide-react";

export default function HomePage() {
  return (
    <div className="min-h-screen bg-[#0D0D0F] text-white">
      {/* Nav */}
      <nav className="fixed top-0 inset-x-0 z-50 bg-[#0D0D0F]/80 backdrop-blur-xl border-b border-white/[0.06]">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-orange-500 rounded-xl flex items-center justify-center shadow-lg shadow-orange-500/30">
              <span className="text-white text-xs font-bold">म</span>
            </div>
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
            Upload your sales data from Tally, Excel, or CSV. Munim analyzes everything in seconds — revenue trends, customer insights, anomalies — and sends WhatsApp reports in your language.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link href="/login"
              className="inline-flex items-center justify-center gap-2 bg-orange-500 hover:bg-orange-600 text-white font-bold text-lg px-8 py-4 rounded-2xl transition-all shadow-xl shadow-orange-500/25 hover:shadow-orange-500/40">
              Start for free <ArrowRight className="w-5 h-5" />
            </Link>
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
              <p className="text-white/40 text-sm mb-4 font-medium">Good morning, Akshit 👋</p>
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
              { icon: Zap,           title: "Instant Analysis",      desc: "Upload any format — Tally XML, Excel, or CSV. Get full AI analysis in under 30 seconds.", color: "bg-orange-500/15 text-orange-400 border-orange-500/20" },
              { icon: TrendingUp,    title: "Smart Insights",        desc: "AI detects anomalies, segments customers, spots dead stock, and surfaces actionable intelligence.", color: "bg-emerald-500/15 text-emerald-400 border-emerald-500/20" },
              { icon: MessageSquare, title: "WhatsApp Reports",      desc: "Get clear business reports on WhatsApp in Hindi, English, or Hinglish — whatever works for you.", color: "bg-blue-500/15 text-blue-400 border-blue-500/20" },
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

      {/* Stats */}
      <section className="py-20 px-6">
        <div className="max-w-4xl mx-auto">
          <div className="grid grid-cols-3 gap-6 text-center">
            {[
              { value: "30s",      label: "Average analysis time" },
              { value: "3",        label: "Supported file formats" },
              { value: "100%",     label: "Powered by AI" },
            ].map((s) => (
              <div key={s.label} className="bg-[#161618] border border-white/[0.07] rounded-3xl p-8">
                <p className="text-5xl font-bold text-white mb-2">{s.value}</p>
                <p className="text-base text-white/40">{s.label}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-24 px-6 bg-[#0A0A0C] border-t border-white/[0.06]">
        <div className="max-w-2xl mx-auto text-center">
          <h2 className="text-4xl font-bold text-white tracking-tight mb-4">
            Start understanding your business today
          </h2>
          <p className="text-lg text-white/40 mb-10">Free to use. No credit card required.</p>
          <Link href="/login"
            className="inline-flex items-center gap-2 bg-orange-500 hover:bg-orange-600 text-white font-bold text-xl px-10 py-5 rounded-2xl transition-all shadow-2xl shadow-orange-500/25 hover:shadow-orange-500/40">
            Get started with Google <ArrowRight className="w-5 h-5" />
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
