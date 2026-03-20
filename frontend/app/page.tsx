import Link from "next/link";
import { ArrowRight, Upload, BarChart3, MessageCircle, CheckCircle2 } from "lucide-react";

const HOW_IT_WORKS = [
  {
    step: "01",
    icon: Upload,
    title: "Upload Your Data",
    desc: "Drag and drop your Tally XML or Excel file. Takes under a minute.",
    iconBg: "bg-saffron",
  },
  {
    step: "02",
    icon: BarChart3,
    title: "AI Analyses Instantly",
    desc: "Revenue trends, top products, dead stock alerts — computed in seconds.",
    iconBg: "bg-forest",
  },
  {
    step: "03",
    icon: MessageCircle,
    title: "Report on WhatsApp",
    desc: "Every Monday 8 AM, your weekly summary lands directly on your phone.",
    iconBg: "bg-golden",
  },
];

const FEATURES = [
  "Hindi, English, and Hinglish reports",
  "Tally XML and Excel support",
  "Revenue anomaly detection",
  "Dead stock alerts",
  "Customer churn warnings",
  "Multi-client CA firm portal",
];

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-cream overflow-hidden">
      {/* Navbar */}
      <nav className="flex items-center justify-between px-6 md:px-16 py-4 sticky top-0 bg-cream/90 backdrop-blur-sm z-10 border-b border-border/50">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-xl bg-forest flex items-center justify-center font-bold text-white text-sm">
            M
          </div>
          <span className="font-bold text-forest text-lg tracking-tight">Munim</span>
        </div>
        <Link
          href="/login"
          className="text-sm font-semibold text-saffron hover:text-saffron-dark transition-colors flex items-center gap-1.5"
        >
          Sign in <ArrowRight className="w-4 h-4" />
        </Link>
      </nav>

      {/* Hero — two column on desktop */}
      <section className="px-6 md:px-16 pt-14 pb-16 md:pt-20 md:pb-24">
        <div className="max-w-6xl mx-auto grid grid-cols-1 md:grid-cols-2 gap-12 items-center">
          {/* Left: copy */}
          <div>
            <div className="inline-flex items-center gap-2 bg-saffron/10 border border-saffron/20 text-saffron text-xs font-semibold px-3 py-1.5 rounded-full mb-6">
              <span className="w-1.5 h-1.5 rounded-full bg-saffron animate-pulse" />
              Free to try — no credit card required
            </div>

            <h1 className="text-4xl md:text-5xl font-bold text-forest leading-[1.15] tracking-tight mb-5">
              Your business data,{" "}
              <span className="text-saffron underline decoration-saffron/40 decoration-4 underline-offset-4">
                explained simply
              </span>
            </h1>

            <p className="text-base text-muted-foreground mb-8 leading-relaxed max-w-md">
              Munim reads your Tally exports, analyses your revenue, and sends you a plain-language WhatsApp report every week. No spreadsheets, no dashboards.
            </p>

            <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4">
              <Link
                href="/login"
                className="inline-flex items-center gap-2.5 bg-saffron hover:bg-saffron-dark text-white font-semibold px-6 py-3 rounded-xl shadow-warm transition-all duration-200 hover:-translate-y-0.5 text-sm"
              >
                Get started with Google
                <ArrowRight className="w-4 h-4" />
              </Link>
              <span className="text-xs text-muted-foreground">Free forever for 1 business</span>
            </div>
          </div>

          {/* Right: WhatsApp phone mockup */}
          <div className="flex justify-center md:justify-end animate-float">
            <div className="bg-forest rounded-3xl p-1.5 shadow-[0_24px_60px_rgba(27,67,50,0.22)] w-full max-w-[280px]">
              <div className="bg-[#128C7E] rounded-2xl p-4 space-y-3">
                {/* WA header */}
                <div className="flex items-center gap-2 border-b border-white/10 pb-3">
                  <div className="w-8 h-8 rounded-full bg-saffron flex items-center justify-center text-white text-xs font-bold">M</div>
                  <div>
                    <p className="text-white text-xs font-semibold">Munim</p>
                    <p className="text-white/50 text-[10px]">online</p>
                  </div>
                </div>
                {/* Message bubble */}
                <div className="bg-white rounded-xl rounded-tl-sm p-3 shadow-sm">
                  <p className="text-[11px] text-gray-700 leading-relaxed hindi">
                    🙏 Namaste Ramesh ji!
                  </p>
                  <p className="text-[11px] text-gray-700 mt-1.5 leading-relaxed">
                    This week revenue:{" "}
                    <span className="text-green-600 font-semibold">₹2,34,500</span>{" "}
                    <span className="text-green-600 font-semibold">📈 +12%</span> vs last week.
                  </p>
                  <p className="text-[11px] text-gray-700 mt-1.5 leading-relaxed">
                    ⚠️ Tata Salt not sold in 18 days. Check your stock.
                  </p>
                  <p className="text-[10px] text-gray-400 mt-2 text-right">8:00 AM ✓✓</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* How it works */}
      <section className="px-6 md:px-16 py-16 bg-white border-y border-border">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-10">
            <h2 className="text-2xl md:text-3xl font-bold text-forest mb-2">
              How it works
            </h2>
            <p className="text-sm text-muted-foreground">
              Setup takes 5 minutes. Everything else is automatic.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            {HOW_IT_WORKS.map((item) => (
              <div
                key={item.step}
                className="border border-border rounded-2xl p-5 bg-white hover:shadow-metric transition-all duration-200 hover:-translate-y-0.5"
              >
                <div className="flex items-start gap-4 mb-3">
                  <div className={`w-10 h-10 rounded-xl ${item.iconBg} flex items-center justify-center flex-shrink-0`}>
                    <item.icon className="w-5 h-5 text-white" />
                  </div>
                  <span className="text-4xl font-black text-border/70 leading-none pt-1">
                    {item.step}
                  </span>
                </div>
                <h3 className="font-bold text-forest text-sm mb-1.5">{item.title}</h3>
                <p className="text-sm text-muted-foreground leading-relaxed">{item.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="px-6 md:px-16 py-16">
        <div className="max-w-6xl mx-auto grid grid-cols-1 md:grid-cols-2 gap-12 items-center">
          <div>
            <h2 className="text-2xl md:text-3xl font-bold text-forest mb-3">
              Everything you need, nothing you don't
            </h2>
            <p className="text-sm text-muted-foreground mb-6">
              Built specifically for Indian small businesses. Works with the tools you already use.
            </p>
            <div className="space-y-2.5">
              {FEATURES.map((f) => (
                <div key={f} className="flex items-center gap-3">
                  <CheckCircle2 className="w-4 h-4 text-saffron flex-shrink-0" />
                  <span className="text-sm text-forest">{f}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            {[
              { label: "Businesses using Munim", value: "1,000+" },
              { label: "Reports sent weekly", value: "4,200+" },
              { label: "Data health score", value: "94/100" },
              { label: "Avg time to first report", value: "4 min" },
            ].map((stat) => (
              <div key={stat.label} className="bg-white border border-border rounded-2xl p-4 text-center">
                <p className="text-2xl font-black text-saffron">{stat.value}</p>
                <p className="text-xs text-muted-foreground mt-1 leading-relaxed">{stat.label}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Final CTA */}
      <section className="px-6 md:px-16 py-16 bg-forest">
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-center justify-between gap-8">
          <div>
            <h2 className="text-2xl md:text-3xl font-bold text-cream mb-2">
              Start for free today
            </h2>
            <p className="text-cream/60 text-sm">
              Your first report is ready in under 5 minutes.
            </p>
          </div>
          <Link
            href="/login"
            className="inline-flex items-center gap-2.5 bg-saffron hover:bg-saffron-dark text-white font-semibold px-7 py-3 rounded-xl shadow-warm transition-all duration-200 hover:-translate-y-0.5 text-sm flex-shrink-0"
          >
            Get started with Google <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="px-6 md:px-16 py-5 bg-forest-dark border-t border-white/5">
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-center justify-between gap-2">
          <p className="text-cream/30 text-xs">2026 Munim. Made for Indian businesses.</p>
          <div className="flex items-center gap-4 text-cream/30 text-xs">
            <Link href="#" className="hover:text-cream/60 transition-colors">Privacy</Link>
            <Link href="#" className="hover:text-cream/60 transition-colors">Terms</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
