import { TrendingUp, TrendingDown, Minus } from "lucide-react";
import { cn } from "@/lib/utils";

interface MetricCardProps {
  label:    string;
  value:    string;
  sub?:     string;
  trend?:   "up" | "down" | "flat" | null;
  trendPct?: string;
  icon?:    React.ReactNode;
  accent?:  "saffron" | "forest" | "golden" | "red" | "orange" | "emerald" | "amber" | "blue" | "purple";
  loading?: boolean;
}

// Accent name → Tailwind classes (supports both legacy and new names)
const ACCENT_STYLES: Record<string, string> = {
  saffron: "border-orange-500/20  bg-gradient-to-br from-orange-500/5  to-transparent",
  orange:  "border-orange-500/20  bg-gradient-to-br from-orange-500/5  to-transparent",
  forest:  "border-emerald-500/20 bg-gradient-to-br from-emerald-500/5 to-transparent",
  emerald: "border-emerald-500/20 bg-gradient-to-br from-emerald-500/5 to-transparent",
  golden:  "border-amber-500/20   bg-gradient-to-br from-amber-500/5   to-transparent",
  amber:   "border-amber-500/20   bg-gradient-to-br from-amber-500/5   to-transparent",
  blue:    "border-blue-500/20    bg-gradient-to-br from-blue-500/5    to-transparent",
  purple:  "border-purple-500/20  bg-gradient-to-br from-purple-500/5  to-transparent",
  red:     "border-red-500/20     bg-gradient-to-br from-red-500/5     to-transparent",
};

const TREND_ICON = {
  up:   <TrendingUp   className="w-3.5 h-3.5" />,
  down: <TrendingDown className="w-3.5 h-3.5" />,
  flat: <Minus        className="w-3.5 h-3.5" />,
};

const TREND_COLOR = {
  up:   "text-emerald-600 bg-emerald-500/10",
  down: "text-red-500     bg-red-500/10",
  flat: "text-muted-foreground bg-secondary",
};

export function MetricCard({
  label, value, sub, trend, trendPct, icon, accent = "saffron", loading,
}: MetricCardProps) {
  if (loading) {
    return (
      <div className="metric-card animate-pulse">
        <div className="skeleton h-4 w-24 mb-4" />
        <div className="skeleton h-8 w-32 mb-2" />
        <div className="skeleton h-3 w-16" />
      </div>
    );
  }

  return (
    <div className={cn("metric-card border rounded-2xl p-5", ACCENT_STYLES[accent])}>
      <div className="flex items-start justify-between mb-3">
        <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
          {label}
        </p>
        {icon && (
          <div className="w-8 h-8 rounded-xl bg-card shadow-sm border border-border/60 flex items-center justify-center">
            {icon}
          </div>
        )}
      </div>

      <p className="text-2xl md:text-3xl font-bold text-foreground mb-2">
        {value}
      </p>

      <div className="flex items-center gap-2 flex-wrap">
        {trend && trendPct && (
          <span className={cn("inline-flex items-center gap-1 text-xs font-semibold px-2 py-0.5 rounded-full", TREND_COLOR[trend])}>
            {TREND_ICON[trend]}
            {trendPct}
          </span>
        )}
        {sub && <span className="text-xs text-muted-foreground">{sub}</span>}
      </div>
    </div>
  );
}
