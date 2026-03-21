"use client";

import { use } from "react";
import {
  useAnalysisMetrics,
  useAnalysisAnomalies,
  useAnalysisCustomers,
} from "@/lib/api/analysis";
import { formatINR, formatDate, trendSymbol } from "@/lib/utils";
import { cn } from "@/lib/utils";
import Link from "next/link";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  Cell,
  PieChart,
  Pie,
  Legend,
} from "recharts";
import {
  ChevronLeft,
  TrendingUp,
  TrendingDown,
  Package,
  Users,
  AlertTriangle,
  CheckCircle2,
  Sparkles,
  Lightbulb,
  Star,
  Zap,
  BarChart2,
  ArrowUpRight,
  ArrowDownRight,
  Upload,
} from "lucide-react";
import type { AiInsight, Anomaly } from "@/lib/types";

// ── Colors ───────────────────────────────────────────────────────────────────

const PIE_COLORS = [
  "#F97316",
  "#10B981",
  "#3B82F6",
  "#8B5CF6",
  "#EF4444",
  "#F59E0B",
];

const INSIGHT_CONFIG: Record<
  AiInsight["type"],
  { border: string; bg: string; icon: React.ReactNode; label: string }
> = {
  opportunity: {
    border: "border-l-green-500",
    bg: "bg-green-500/5",
    icon: <Lightbulb className="w-4 h-4 text-green-400" />,
    label: "Opportunity",
  },
  warning: {
    border: "border-l-amber-500",
    bg: "bg-amber-500/5",
    icon: <AlertTriangle className="w-4 h-4 text-amber-400" />,
    label: "Warning",
  },
  celebration: {
    border: "border-l-orange-500",
    bg: "bg-orange-500/5",
    icon: <Star className="w-4 h-4 text-orange-400" />,
    label: "Celebrating",
  },
  action: {
    border: "border-l-blue-500",
    bg: "bg-blue-500/5",
    icon: <Zap className="w-4 h-4 text-blue-400" />,
    label: "Action",
  },
};

// ── Skeleton ──────────────────────────────────────────────────────────────────

function Skeleton({ h = "h-4", w = "w-full", className = "" }: { h?: string; w?: string; className?: string }) {
  return <div className={cn("skeleton rounded-xl", h, w, className)} />;
}

// ── Tooltip ───────────────────────────────────────────────────────────────────

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-card border border-border rounded-xl px-3 py-2 shadow-lg">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="text-sm font-bold text-foreground">
        {formatINR(payload[0].value)}
      </p>
    </div>
  );
};

// ── KPI Card ──────────────────────────────────────────────────────────────────

function KpiCard({
  label,
  value,
  sub,
  trend,
  accent = "orange",
}: {
  label: string;
  value: string;
  sub?: string;
  trend?: "up" | "down" | "flat" | null;
  accent?: "orange" | "green" | "red" | "blue";
}) {
  const accentMap = {
    orange: "from-orange-500/10 to-orange-500/5 border-orange-500/20",
    green:  "from-green-500/10 to-green-500/5 border-green-500/20",
    red:    "from-red-500/10 to-red-500/5 border-red-500/20",
    blue:   "from-blue-500/10 to-blue-500/5 border-blue-500/20",
  };
  const textMap = {
    orange: "text-orange-400",
    green:  "text-green-400",
    red:    "text-red-400",
    blue:   "text-blue-400",
  };

  return (
    <div
      className={cn(
        "rounded-2xl p-4 border bg-gradient-to-br",
        accentMap[accent]
      )}
    >
      <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1">
        {label}
      </p>
      <p className={cn("text-2xl font-black", textMap[accent])}>{value}</p>
      {sub && (
        <div className="flex items-center gap-1 mt-1">
          {trend === "up" && <ArrowUpRight className="w-3.5 h-3.5 text-green-400" />}
          {trend === "down" && <ArrowDownRight className="w-3.5 h-3.5 text-red-400" />}
          <p className="text-xs text-muted-foreground truncate">{sub}</p>
        </div>
      )}
    </div>
  );
}

// ── Section Title ─────────────────────────────────────────────────────────────

function SectionTitle({ children, icon }: { children: React.ReactNode; icon?: React.ReactNode }) {
  return (
    <div className="flex items-center gap-2 mb-4">
      {icon && <span className="flex-shrink-0">{icon}</span>}
      <h2 className="text-base font-bold text-foreground">{children}</h2>
    </div>
  );
}

// ── Revenue + Products Charts ──────────────────────────────────────────────────

function ChartsSection({ uploadId }: { uploadId: string }) {
  const { data, isLoading } = useAnalysisMetrics(uploadId);

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 bg-card border border-border rounded-2xl p-5">
          <Skeleton h="h-6" w="w-40" className="mb-4" />
          <Skeleton h="h-56" />
        </div>
        <div className="bg-card border border-border rounded-2xl p-5">
          <Skeleton h="h-6" w="w-32" className="mb-4" />
          <div className="space-y-3">
            {Array(5).fill(0).map((_, i) => <Skeleton key={i} h="h-8" />)}
          </div>
        </div>
      </div>
    );
  }

  if (!data) return null;

  const trend = data.revenue_trend ?? [];
  const products = data.top_products ?? [];
  const maxRev = products[0]?.revenue ?? 1;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
      {/* Revenue Area Chart */}
      <div className="lg:col-span-2 bg-card border border-border rounded-2xl p-5">
        <SectionTitle icon={<BarChart2 className="w-4 h-4 text-orange-400" />}>
          Revenue Trend
        </SectionTitle>

        {trend.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-48 text-center">
            <Upload className="w-10 h-10 text-muted-foreground/40 mb-3" />
            <p className="text-sm text-muted-foreground">No daily trend data available</p>
            <p className="text-xs text-muted-foreground/60 mt-1">
              Upload a file with daily transaction records to see the trend chart
            </p>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={trend} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="revenueGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor="#F97316" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#F97316" stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
              <XAxis
                dataKey="date"
                tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
                tickLine={false}
                axisLine={false}
                tickFormatter={(v) => {
                  try {
                    return new Date(v).toLocaleDateString("en-IN", { day: "numeric", month: "short" });
                  } catch {
                    return v;
                  }
                }}
                interval="preserveStartEnd"
              />
              <YAxis
                tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
                tickLine={false}
                axisLine={false}
                tickFormatter={(v) => formatINR(v, true)}
                width={60}
              />
              <Tooltip content={<CustomTooltip />} />
              <Area
                type="monotone"
                dataKey="revenue"
                stroke="#F97316"
                strokeWidth={2}
                fill="url(#revenueGrad)"
                dot={false}
                activeDot={{ r: 4, fill: "#F97316" }}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Top Products Bar Chart */}
      {products.length > 0 ? (
        <div className="bg-card border border-border rounded-2xl p-5">
          <SectionTitle icon={<Package className="w-4 h-4 text-orange-400" />}>
            Top Products
          </SectionTitle>
          <div className="space-y-3">
            {products.slice(0, 5).map((p, i) => (
              <div key={i}>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-medium text-foreground truncate max-w-[140px]">
                    {p.name}
                  </span>
                  <span className="text-xs font-bold text-orange-400 ml-2 flex-shrink-0">
                    {formatINR(p.revenue, true)}
                  </span>
                </div>
                <div className="h-1.5 bg-muted rounded-full overflow-hidden">
                  <div
                    className="h-full bg-orange-500 rounded-full transition-all duration-700"
                    style={{ width: `${Math.max(4, (p.revenue / maxRev) * 100)}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div className="bg-card border border-border rounded-2xl p-5 flex flex-col items-center justify-center text-center">
          <Package className="w-8 h-8 text-muted-foreground/40 mb-2" />
          <p className="text-sm text-muted-foreground">No product data</p>
        </div>
      )}
    </div>
  );
}

// ── AI Insights ────────────────────────────────────────────────────────────────

function AiInsightsSection({ uploadId }: { uploadId: string }) {
  const { data, isLoading } = useAnalysisMetrics(uploadId);

  return (
    <div>
      <SectionTitle icon={<Sparkles className="w-4 h-4 text-orange-400" />}>
        AI Insights
      </SectionTitle>

      {isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {Array(4).fill(0).map((_, i) => (
            <div key={i} className="bg-card border border-border rounded-2xl p-4 border-l-4 border-l-muted">
              <Skeleton h="h-4" w="w-32" className="mb-2" />
              <Skeleton h="h-3" className="mb-1" />
              <Skeleton h="h-3" w="w-4/5" />
            </div>
          ))}
        </div>
      ) : !data ? null : data.ai_insights?.length === 0 ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {Array(4).fill(0).map((_, i) => (
            <div key={i} className="bg-card border border-border rounded-2xl p-4 border-l-4 border-l-muted animate-pulse">
              <div className="flex items-center gap-2 mb-2">
                <Sparkles className="w-4 h-4 text-muted-foreground/40" />
                <div className="h-3 bg-muted rounded w-24" />
              </div>
              <div className="h-2.5 bg-muted rounded w-full mb-1.5" />
              <div className="h-2.5 bg-muted rounded w-3/4" />
              <p className="text-xs text-muted-foreground/50 mt-2">AI Insights are generating...</p>
            </div>
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {data.ai_insights.map((insight, i) => {
            const cfg = INSIGHT_CONFIG[insight.type] ?? INSIGHT_CONFIG.action;
            return (
              <div
                key={i}
                className={cn(
                  "bg-card border border-border border-l-4 rounded-2xl p-4",
                  cfg.border,
                  cfg.bg,
                )}
              >
                <div className="flex items-center gap-2 mb-2">
                  {cfg.icon}
                  <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                    {cfg.label}
                  </span>
                </div>
                <p className="text-sm font-bold text-foreground mb-1 leading-snug">
                  {insight.title}
                </p>
                <p className="text-sm text-muted-foreground leading-relaxed">
                  {insight.insight}
                </p>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ── Customer Segments ─────────────────────────────────────────────────────────

function CustomersSection({ uploadId }: { uploadId: string }) {
  const { data, isLoading } = useAnalysisCustomers(uploadId);

  if (isLoading) {
    return (
      <div>
        <SectionTitle icon={<Users className="w-4 h-4 text-orange-400" />}>Customers</SectionTitle>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="bg-card border border-border rounded-2xl p-5">
            <Skeleton h="h-48" />
          </div>
          <div className="bg-card border border-border rounded-2xl p-5 space-y-3">
            {Array(5).fill(0).map((_, i) => <Skeleton key={i} h="h-10" />)}
          </div>
        </div>
      </div>
    );
  }

  if (!data) return null;

  const segments = Object.entries(data.segments)
    .filter(([, v]) => v && v > 0)
    .map(([name, value]) => ({ name, value: value as number }));

  const topCustomers = data.top_customers ?? [];
  const maxCustomerRev = topCustomers[0]
    ? (topCustomers[0] as any).revenue ?? 1
    : 1;

  return (
    <div>
      <SectionTitle icon={<Users className="w-4 h-4 text-orange-400" />}>
        Customers
      </SectionTitle>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Donut chart */}
        <div className="bg-card border border-border rounded-2xl p-5">
          <div className="flex items-center justify-between mb-3">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              Segment Distribution
            </p>
            <p className="text-lg font-black text-orange-400">{data.total_customers}</p>
          </div>
          {segments.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie
                  data={segments}
                  cx="50%"
                  cy="50%"
                  innerRadius={55}
                  outerRadius={80}
                  dataKey="value"
                  paddingAngle={2}
                >
                  {segments.map((_, idx) => (
                    <Cell
                      key={idx}
                      fill={PIE_COLORS[idx % PIE_COLORS.length]}
                    />
                  ))}
                </Pie>
                <Legend
                  iconType="circle"
                  iconSize={8}
                  formatter={(value) => (
                    <span className="text-xs text-muted-foreground">{value}</span>
                  )}
                />
                <Tooltip
                  formatter={(v: any) => [v, "customers"]}
                  contentStyle={{
                    background: "hsl(var(--card))",
                    border: "1px solid hsl(var(--border))",
                    borderRadius: "12px",
                    fontSize: 12,
                  }}
                />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex items-center justify-center h-40 text-sm text-muted-foreground">
              No segment data
            </div>
          )}
        </div>

        {/* Top customers */}
        <div className="bg-card border border-border rounded-2xl p-5">
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">
            Top Customers
          </p>
          {topCustomers.length === 0 ? (
            <p className="text-sm text-muted-foreground">No customer data</p>
          ) : (
            <div className="space-y-3">
              {topCustomers.slice(0, 6).map((c, i) => {
                const rev = (c as any).revenue ?? 0;
                return (
                  <div key={i}>
                    <div className="flex items-center justify-between mb-0.5">
                      <div className="flex items-center gap-2">
                        <div className="w-6 h-6 rounded-full bg-orange-500/10 flex items-center justify-center text-xs font-bold text-orange-400 flex-shrink-0">
                          {c.name.slice(0, 1).toUpperCase()}
                        </div>
                        <span className="text-sm font-medium text-foreground truncate max-w-[140px]">
                          {c.name}
                        </span>
                      </div>
                      <span className="text-xs font-bold text-muted-foreground ml-2 flex-shrink-0">
                        {formatINR(rev, true)}
                      </span>
                    </div>
                    {rev > 0 && (
                      <div className="h-1 bg-muted rounded-full overflow-hidden ml-8">
                        <div
                          className="h-full bg-orange-500/50 rounded-full"
                          style={{ width: `${Math.max(4, (rev / maxCustomerRev) * 100)}%` }}
                        />
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Anomalies ─────────────────────────────────────────────────────────────────

function AnomaliesSection({ uploadId }: { uploadId: string }) {
  const { data, isLoading } = useAnalysisAnomalies(uploadId);

  if (isLoading) {
    return (
      <div>
        <SectionTitle icon={<AlertTriangle className="w-4 h-4 text-amber-400" />}>
          Alerts
        </SectionTitle>
        <div className="space-y-3">
          {Array(2).fill(0).map((_, i) => <Skeleton key={i} h="h-20" />)}
        </div>
      </div>
    );
  }

  if (!data || data.anomalies.length === 0) {
    return (
      <div>
        <SectionTitle icon={<AlertTriangle className="w-4 h-4 text-amber-400" />}>
          Alerts
        </SectionTitle>
        <div className="bg-card border border-border rounded-2xl p-6 flex flex-col items-center text-center">
          <CheckCircle2 className="w-10 h-10 text-green-500 mb-3" />
          <p className="font-semibold text-foreground">All clear</p>
          <p className="text-sm text-muted-foreground mt-1">No anomalies detected this period</p>
        </div>
      </div>
    );
  }

  const SEVERITY_STYLE: Record<string, string> = {
    HIGH:   "border-l-red-500 bg-red-500/5",
    MEDIUM: "border-l-amber-500 bg-amber-500/5",
    LOW:    "border-l-blue-500 bg-blue-500/5",
  };
  const BADGE_STYLE: Record<string, string> = {
    HIGH:   "badge-high",
    MEDIUM: "badge-medium",
    LOW:    "badge-low",
  };

  return (
    <div>
      <SectionTitle icon={<AlertTriangle className="w-4 h-4 text-amber-400" />}>
        Alerts
      </SectionTitle>

      {/* Summary */}
      <div className="flex gap-3 flex-wrap mb-4">
        {data.high_count > 0   && <span className="badge-high">HIGH: {data.high_count}</span>}
        {data.medium_count > 0 && <span className="badge-medium">MEDIUM: {data.medium_count}</span>}
        {data.low_count > 0    && <span className="badge-low">LOW: {data.low_count}</span>}
      </div>

      <div className="space-y-3">
        {data.anomalies.map((a: Anomaly, i: number) => (
          <div
            key={i}
            className={cn(
              "bg-card border border-border border-l-4 rounded-2xl p-4",
              SEVERITY_STYLE[a.severity] ?? ""
            )}
          >
            <div className="flex items-start gap-3">
              <AlertTriangle
                className={cn(
                  "w-4 h-4 mt-0.5 flex-shrink-0",
                  a.severity === "HIGH"   ? "text-red-400"   : "",
                  a.severity === "MEDIUM" ? "text-amber-400" : "",
                  a.severity === "LOW"    ? "text-blue-400"  : "",
                )}
              />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1 flex-wrap">
                  <p className="font-semibold text-sm text-foreground">{a.title}</p>
                  <span className={BADGE_STYLE[a.severity] ?? ""}>{a.severity}</span>
                </div>
                <p className="text-sm text-muted-foreground leading-relaxed">{a.explanation}</p>
                {a.action && (
                  <p className="text-xs font-semibold text-orange-400 mt-2">
                    &rarr; {a.action}
                  </p>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Dead Stock ────────────────────────────────────────────────────────────────

function DeadStockSection({ uploadId }: { uploadId: string }) {
  const { data, isLoading } = useAnalysisMetrics(uploadId);

  if (isLoading || !data || data.dead_stock_count === 0) return null;

  return (
    <div>
      <SectionTitle icon={<Package className="w-4 h-4 text-amber-400" />}>
        Dead Stock ({data.dead_stock_count} items)
      </SectionTitle>
      <div className="bg-amber-500/10 border border-amber-500/20 rounded-2xl p-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {data.dead_stock.map((item, i) => (
            <div
              key={i}
              className="flex items-center justify-between bg-card border border-border rounded-xl px-3 py-2.5"
            >
              <span className="text-sm font-medium text-amber-300 truncate max-w-[160px]">
                {item.product}
              </span>
              <span className="text-xs font-bold text-amber-400 ml-2 flex-shrink-0 bg-amber-500/15 px-2 py-0.5 rounded-full">
                {item.days_since_last_sale}d
              </span>
            </div>
          ))}
        </div>
        <p className="text-xs text-amber-500/70 mt-3 text-center">
          These items have not sold in {data.dead_stock[0]?.days_since_last_sale ?? 14}+ days. Consider discounting or bundling them.
        </p>
      </div>
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

type Params = Promise<{ id: string }>;

export default function AnalysisPage({ params }: { params: Params }) {
  const { id: uploadId } = use(params);
  const { data: metrics, isLoading: metricsLoading } = useAnalysisMetrics(uploadId);

  const isUp = metrics?.revenue?.trend === "up";
  const changeAccent = metrics
    ? isUp
      ? "green"
      : metrics.revenue.trend === "down"
      ? "red"
      : "blue"
    : "blue";

  return (
    <div className="max-w-5xl mx-auto animate-fade-in pb-12">
      {/* Back */}
      <Link
        href="/dashboard"
        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors mb-5"
      >
        <ChevronLeft className="w-4 h-4" />
        Dashboard
      </Link>

      {/* Header */}
      <div className="flex items-start justify-between gap-4 mb-6 flex-wrap">
        <div>
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <h1 className="text-xl font-bold text-foreground">Business Analysis</h1>
            {metrics?.business_type && metrics.business_type !== "business" && (
              <span className="text-xs font-semibold bg-orange-500/10 text-orange-400 border border-orange-500/20 px-2.5 py-0.5 rounded-full capitalize">
                {metrics.business_type}
              </span>
            )}
          </div>
          {metrics && (
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <span>{formatDate(metrics.period_start)}</span>
              <span>&rarr;</span>
              <span>{formatDate(metrics.period_end)}</span>
              {metrics.period_label && (
                <>
                  <span>&middot;</span>
                  <span className="text-muted-foreground/70">{metrics.period_label}</span>
                </>
              )}
            </div>
          )}
        </div>
        <Link
          href="/reports"
          className="inline-flex items-center gap-1.5 bg-orange-500 hover:bg-orange-600 text-white text-xs font-semibold px-4 py-2 rounded-xl transition-colors flex-shrink-0"
        >
          Generate Report
        </Link>
      </div>

      {/* KPI Cards */}
      {metricsLoading ? (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
          {Array(4).fill(0).map((_, i) => <Skeleton key={i} h="h-24" />)}
        </div>
      ) : metrics ? (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
          <KpiCard
            label="Period Revenue"
            value={formatINR(metrics.revenue.current, true)}
            sub={`vs ${formatINR(metrics.revenue.previous, true)}`}
            trend={metrics.revenue.trend}
            accent="orange"
          />
          <KpiCard
            label="Change"
            value={trendSymbol(metrics.revenue.change_pct)}
            sub={metrics.revenue.trend === "up" ? "Growing" : metrics.revenue.trend === "down" ? "Declining" : "Stable"}
            trend={metrics.revenue.trend}
            accent={changeAccent as any}
          />
          <KpiCard
            label="Products"
            value={String(metrics.top_products?.length ?? 0)}
            sub="tracked items"
            accent="blue"
          />
          <KpiCard
            label="Dead Stock"
            value={String(metrics.dead_stock_count ?? 0)}
            sub={metrics.dead_stock_count > 0 ? "items not selling" : "items — all good"}
            accent={metrics.dead_stock_count > 0 ? "red" : "green"}
          />
        </div>
      ) : null}

      {/* Charts */}
      <div className="mb-6">
        <ChartsSection uploadId={uploadId} />
      </div>

      {/* AI Insights */}
      <div className="mb-6">
        <AiInsightsSection uploadId={uploadId} />
      </div>

      {/* Customer Segments */}
      <div className="mb-6">
        <CustomersSection uploadId={uploadId} />
      </div>

      {/* Anomalies */}
      <div className="mb-6">
        <AnomaliesSection uploadId={uploadId} />
      </div>

      {/* Dead Stock */}
      <DeadStockSection uploadId={uploadId} />
    </div>
  );
}
