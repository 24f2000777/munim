import Link from "next/link";
import { ArrowRight, Upload, BarChart3, MessageCircle, CheckCircle2 } from "lucide-react";

const HOW_IT_WORKS = [
  {
    step: "01",
    icon: Upload,
    title: "Upload karein",
    titleEn: "Upload Your Data",
    desc: "Tally ka XML ya Excel file — bas drag karke upload karo.",
    color: "bg-saffron/10 text-saffron border-saffron/20",
    iconBg: "bg-saffron",
  },
  {
    step: "02",
    icon: BarChart3,
    title: "AI analyse karta hai",
    titleEn: "AI Analyses Instantly",
    desc: "Revenue trends, top products, dead stock — sab kuch ek second mein.",
    color: "bg-forest/10 text-forest border-forest/20",
    iconBg: "bg-forest",
  },
  {
    step: "03",
    icon: MessageCircle,
    title: "WhatsApp pe aata hai",
    titleEn: "Report on WhatsApp",
    desc: "Har Somvar subah 8 baje — apni report seedha phone pe.",
    color: "bg-golden/10 text-golden-dark border-golden/20",
    iconBg: "bg-golden",
  },
];

const FEATURES = [
  "Hindi, English, aur Hinglish mein",
  "Tally XML aur Excel support",
  "Revenue anomalies auto-detect",
  "Dead stock alerts",
  "Customer churn warning",
  "CA firm ke liye multi-client",
];

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-cream overflow-hidden">
      {/* ── Navbar ─────────────────────────────────────────────────────── */}
      <nav className="flex items-center justify-between px-6 md:px-12 py-4 sticky top-0 bg-cream/90 backdrop-blur-sm z-10 border-b border-border/50">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-xl bg-forest flex items-center justify-center font-bold text-white text-sm">
            म
          </div>
          <span className="font-bold text-forest text-lg tracking-tight">Munim</span>
        </div>
        <Link
          href="/login"
          className="text-sm font-semibold text-saffron hover:text-saffron-dark transition-colors flex items-center gap-1.5"
        >
          Login karo <ArrowRight className="w-4 h-4" />
        </Link>
      </nav>

      {/* ── Hero ──────────────────────────────────────────────────────── */}
      <section className="relative px-6 md:px-12 pt-16 md:pt-24 pb-20 md:pb-28 overflow-hidden">
        {/* Decorative blobs */}
        <div className="absolute top-0 right-0 w-96 h-96 bg-saffron/8 rounded-full blur-3xl -translate-y-1/2 translate-x-1/3 pointer-events-none" />
        <div className="absolute bottom-0 left-0 w-72 h-72 bg-forest/6 rounded-full blur-3xl translate-y-1/3 -translate-x-1/4 pointer-events-none" />

        <div className="max-w-4xl mx-auto text-center relative">
          {/* Badge */}
          <div className="inline-flex items-center gap-2 bg-saffron/10 border border-saffron/20 text-saffron text-xs font-semibold px-4 py-1.5 rounded-full mb-6 animate-fade-in">
            <span className="w-1.5 h-1.5 rounded-full bg-saffron animate-pulse" />
            Ab available hai — Free mein try karo
          </div>

          {/* Main headline */}
          <h1 className="text-4xl md:text-6xl font-bold text-forest leading-tight tracking-tight mb-6 animate-fade-in">
            Apne business ki{" "}
            <span className="relative inline-block">
              <span className="text-saffron">poori tasveer</span>
              <svg
                className="absolute -bottom-1 left-0 w-full"
                viewBox="0 0 300 8"
                fill="none"
                preserveAspectRatio="none"
              >
                <path
                  d="M0 6 Q75 1 150 5 Q225 9 300 4"
                  stroke="#E8651A"
                  strokeWidth="3"
                  strokeLinecap="round"
                  fill="none"
                  opacity="0.5"
                />
              </svg>
            </span>
            {" "}—{" "}
            <span className="hindi">एक नज़र में</span>
          </h1>

          <p className="text-base md:text-lg text-muted-foreground max-w-2xl mx-auto mb-10 leading-relaxed animate-slide-up">
            Munim aapka Tally data padhta hai, analyse karta hai, aur har week
            WhatsApp pe Hindi mein report bhejta hai.{" "}
            <strong className="text-forest">Koi technical knowledge nahi chahiye.</strong>
          </p>

          {/* CTA */}
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4 animate-slide-up">
            <Link
              href="/login"
              className="inline-flex items-center gap-2.5 bg-saffron hover:bg-saffron-dark text-white font-semibold px-7 py-3.5 rounded-xl shadow-warm transition-all duration-200 hover:-translate-y-0.5 hover:shadow-glow text-base"
            >
              Google se shuru karo
              <ArrowRight className="w-4 h-4" />
            </Link>
            <span className="text-sm text-muted-foreground">
              Free hai • Credit card nahi chahiye
            </span>
          </div>
        </div>

        {/* Hero visual — phone mockup */}
        <div className="mt-16 max-w-sm mx-auto animate-float">
          <div className="bg-forest rounded-3xl p-1.5 shadow-[0_32px_80px_rgba(27,67,50,0.25)]">
            <div className="bg-[#128C7E] rounded-2xl p-4 space-y-3">
              {/* WhatsApp header */}
              <div className="flex items-center gap-2 border-b border-white/10 pb-3">
                <div className="w-8 h-8 rounded-full bg-saffron flex items-center justify-center text-white text-xs font-bold">म</div>
                <div>
                  <p className="text-white text-xs font-semibold">Munim</p>
                  <p className="text-white/60 text-[10px]">online</p>
                </div>
              </div>
              {/* Message bubble */}
              <div className="bg-white rounded-xl rounded-tl-sm p-3 shadow-sm max-w-[85%]">
                <p className="text-[11px] text-gray-800 leading-relaxed hindi">
                  🙏 नमस्ते Ramesh जी!
                </p>
                <p className="text-[11px] text-gray-700 mt-1 leading-relaxed hindi">
                  इस हफ्ते आपकी revenue{" "}
                  <span className="text-green-600 font-semibold">₹2,34,500</span> रही — पिछले हफ्ते से{" "}
                  <span className="text-green-600 font-semibold">📈 12% ज़्यादा</span>।
                </p>
                <p className="text-[11px] text-gray-700 mt-2 leading-relaxed hindi">
                  ⚠️ Tata Salt 18 दिनों से नहीं बिका — check करें।
                </p>
                <p className="text-[10px] text-gray-400 mt-2 text-right">8:00 AM ✓✓</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── How it works ─────────────────────────────────────────────── */}
      <section className="px-6 md:px-12 py-20 bg-white border-y border-border">
        <div className="max-w-5xl mx-auto">
          <h2 className="text-2xl md:text-3xl font-bold text-forest text-center mb-3">
            Teen simple steps
          </h2>
          <p className="text-muted-foreground text-center mb-12 text-sm">
            Setup mein 5 minutes lagte hain — phir sab auto-pilot pe
          </p>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {HOW_IT_WORKS.map((item) => (
              <div
                key={item.step}
                className="relative border border-border rounded-2xl p-6 bg-white hover:shadow-metric transition-all duration-200 hover:-translate-y-1"
              >
                <div className="flex items-start gap-4 mb-4">
                  <div className={`w-10 h-10 rounded-xl ${item.iconBg} flex items-center justify-center shadow-sm flex-shrink-0`}>
                    <item.icon className="w-5 h-5 text-white" />
                  </div>
                  <span className="text-4xl font-black text-border/80 leading-none pt-0.5">
                    {item.step}
                  </span>
                </div>
                <h3 className="font-bold text-forest text-base mb-1">{item.title}</h3>
                <p className="text-xs text-muted-foreground font-medium mb-2">{item.titleEn}</p>
                <p className="text-sm text-muted-foreground leading-relaxed">{item.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Features grid ────────────────────────────────────────────── */}
      <section className="px-6 md:px-12 py-20">
        <div className="max-w-4xl mx-auto">
          <h2 className="text-2xl md:text-3xl font-bold text-forest text-center mb-10">
            Jo milta hai Munim mein
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {FEATURES.map((f) => (
              <div key={f} className="flex items-center gap-3 bg-white border border-border rounded-xl px-4 py-3">
                <CheckCircle2 className="w-5 h-5 text-saffron flex-shrink-0" />
                <span className="text-sm font-medium text-forest">{f}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Final CTA ────────────────────────────────────────────────── */}
      <section className="px-6 md:px-12 py-20 bg-forest text-center">
        <div className="max-w-2xl mx-auto">
          <div className="w-14 h-14 rounded-2xl bg-saffron flex items-center justify-center mx-auto mb-6 shadow-warm">
            <span className="text-2xl font-black text-white hindi">म</span>
          </div>
          <h2 className="text-2xl md:text-3xl font-bold text-cream mb-4">
            Aaj hi shuru karo
          </h2>
          <p className="text-cream/70 text-sm mb-8">
            Hazar se zyada vyapari apna data samajhte hain Munim ke saath.
          </p>
          <Link
            href="/login"
            className="inline-flex items-center gap-2.5 bg-saffron hover:bg-saffron-dark text-white font-semibold px-8 py-3.5 rounded-xl shadow-warm transition-all duration-200 hover:-translate-y-0.5 text-base"
          >
            Free mein shuru karo <ArrowRight className="w-4 h-4" />
          </Link>
          <p className="text-cream/40 text-xs mt-4 hindi">आपका digital मुनीम 🙏</p>
        </div>
      </section>

      {/* ── Footer ───────────────────────────────────────────────────── */}
      <footer className="px-6 md:px-12 py-6 bg-forest-dark border-t border-white/5">
        <div className="max-w-5xl mx-auto flex flex-col md:flex-row items-center justify-between gap-2">
          <p className="text-cream/30 text-xs">© 2026 Munim. Made with ❤️ for Indian businesses.</p>
          <div className="flex items-center gap-4 text-cream/30 text-xs">
            <Link href="#" className="hover:text-cream/60 transition-colors">Privacy</Link>
            <Link href="#" className="hover:text-cream/60 transition-colors">Terms</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
