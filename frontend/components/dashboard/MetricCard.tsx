import { TrendingUp, TrendingDown, Minus } from "lucide-react";
import { cn } from "@/lib/utils";

interface MetricCardProps {
  label:    string;
  value:    string;
  sub?:     string;
  trend?:   "up" | "down" | "flat" | null;
  trendPct?: string;
  icon?:    React.ReactNode;
  accent?:  "saffron" | "forest" | "golden" | "red";
  loading?: boolean;
}

const ACCENT_STYLES = {
  saffron: "border-saffron/20 bg-gradient-to-br from-saffron/5 to-transparent",
  forest:  "border-forest/20 bg-gradient-to-br from-forest/5 to-transparent",
  golden:  "border-golden/20 bg-gradient-to-br from-golden/5 to-transparent",
  red:     "border-red-200 bg-gradient-to-br from-red-50 to-transparent",
};

const TREND_ICON = {
  up:   <TrendingUp className="w-3.5 h-3.5" />,
  down: <TrendingDown className="w-3.5 h-3.5" />,
  flat: <Minus className="w-3.5 h-3.5" />,
};

const TREND_COLOR = {
  up:   "text-green-600 bg-green-50",
  down: "text-red-600 bg-red-50",
  flat: "text-muted-foreground bg-muted",
};

export function MetricCard({
  label, value, sub, trend, trendPct, icon, accent = "saffron", loading,
}: MetricCardProps) {
  if (loading) {
    return (
      <div className="metric-card">
        <div className="skeleton h-4 w-24 mb-4" />
        <div className="skeleton h-8 w-32 mb-2" />
        <div className="skeleton h-3 w-16" />
      </div>
    );
  }

  return (
    <div className={cn("metric-card border", ACCENT_STYLES[accent])}>
      <div className="flex items-start justify-between mb-3">
        <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
          {label}
        </p>
        {icon && (
          <div className="w-8 h-8 rounded-lg bg-white shadow-sm border border-border/60 flex items-center justify-center">
            {icon}
          </div>
        )}
      </div>

      <p className="text-2xl md:text-3xl font-bold text-foreground mb-2 animate-count-up">
        {value}
      </p>

      <div className="flex items-center gap-2 flex-wrap">
        {trend && trendPct && (
          <span
            className={cn(
              "inline-flex items-center gap-1 text-xs font-semibold px-2 py-0.5 rounded-full",
              TREND_COLOR[trend]
            )}
          >
            {TREND_ICON[trend]}
            {trendPct}
          </span>
        )}
        {sub && (
          <span className="text-xs text-muted-foreground">{sub}</span>
        )}
      </div>
    </div>
  );
}
