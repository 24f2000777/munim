"use client";
import { useSession } from "next-auth/react";
import Link from "next/link";
import {
  TrendingUp, TrendingDown, Upload, FileText,
  Users, Activity, ArrowRight, AlertTriangle,
  IndianRupee, Package, Star, Plus,
} from "lucide-react";
import { useAnalysisHistory, useAnalysisMetrics } from "@/lib/api/analysis";
import { formatINR, relativeTime } from "@/lib/utils";
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from "recharts";

function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-card border border-border rounded-2xl px-4 py-3 shadow-xl text-sm">
      <p className="text-muted-foreground mb-1">{label}</p>
      <p className="font-bold text-foreground text-lg">{formatINR(payload[0].value)}</p>
    </div>
  );
}

function MetricCard({
  label, value, change, trend, icon: Icon, variant,
}: {
  label:   string;
  value:   string;
  change:  string;
  trend:   "up" | "down" | "neutral";
  icon:    any;
  variant: "orange" | "emerald" | "blue" | "purple";
}) {
  const variants = {
    orange:  { card: "metric-orange",  icon: "bg-orange-500/20 text-orange-400",   badge: "bg-orange-500/15 text-orange-400"  },
    emerald: { card: "metric-emerald", icon: "bg-emerald-500/20 text-emerald-400", badge: "bg-emerald-500/15 text-emerald-400" },
    blue:    { card: "metric-blue",    icon: "bg-blue-500/20 text-blue-400",       badge: "bg-blue-500/15 text-blue-400"      },
    purple:  { card: "metric-purple",  icon: "bg-purple-500/20 text-purple-400",   badge: "bg-purple-500/15 text-purple-400"  },
  };
  const v = variants[variant];
  return (
    <div className={`metric-card ${v.card} border rounded-2xl p-6`}>
      <div className="flex items-start justify-between mb-5">
        <div className={`w-11 h-11 rounded-2xl flex items-center justify-center ${v.icon}`}>
          <Icon className="w-5 h-5" />
        </div>
        <span className={`inline-flex items-center gap-1.5 text-sm font-semibold px-3 py-1 rounded-full ${v.badge}`}>
          {trend === "up"   && <TrendingUp   className="w-3.5 h-3.5" />}
          {trend === "down" && <TrendingDown className="w-3.5 h-3.5" />}
          {change}
        </span>
      </div>
      <p className="text-3xl font-bold text-foreground tracking-tight mb-1.5">{value}</p>
      <p className="text-base text-muted-foreground">{label}</p>
    </div>
  );
}

function MetricSkeleton({ variant }: { variant: "orange" | "emerald" | "blue" | "purple" }) {
  return (
    <div className={`metric-card metric-${variant} border rounded-2xl p-6 animate-pulse`}>
      <div className="flex items-start justify-between mb-5">
        <div className="w-11 h-11 rounded-2xl bg-secondary" />
        <div className="h-7 w-16 rounded-full bg-secondary" />
      </div>
      <div className="h-9 w-32 rounded-lg bg-secondary mb-1.5" />
      <div className="h-5 w-24 rounded bg-secondary" />
    </div>
  );
}

export default function DashboardPage() {
  const { data: session } = useSession();
  const firstName = session?.user?.name?.split(" ")[0] ?? "there";
  const hour      = new Date().getHours();
  const greeting  = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";

  // Recent uploads list
  const { data: history } = useAnalysisHistory(1, 5);
  const analyses = history?.items ?? [];

  // Metrics from the most recent upload
  const latestId  = analyses[0]?.upload_id ?? "";
  const { data: metrics, isLoading: metricsLoading } = useAnalysisMetrics(latestId);

  // Chart: use real revenue_trend data
  const chartData = (metrics?.revenue_trend ?? []).map((p) => ({
    label:   new Date(p.date).toLocaleDateString("en-IN", { day: "numeric", month: "short" }),
    revenue: p.revenue,
  }));

  // Derived KPI values
  const revenue    = metrics ? formatINR(metrics.revenue.current)       : "—";
  const changePct  = metrics?.revenue.change_pct != null
    ? `${metrics.revenue.change_pct > 0 ? "+" : ""}${metrics.revenue.change_pct.toFixed(1)}%`
    : "—";
  const revTrend   = (metrics?.revenue.trend === "up" ? "up" : metrics?.revenue.trend === "down" ? "down" : "neutral") as "up" | "down" | "neutral";
  const healthScore = analyses[0]?.health_score;
  const healthLabel = healthScore == null ? "—" : `${healthScore}/100`;
  const healthBadge = healthScore == null ? "—" : healthScore >= 80 ? "Excellent" : healthScore >= 60 ? "Good" : "Needs work";
  const healthTrend = (healthScore != null && healthScore >= 60 ? "up" : "down") as "up" | "down" | "neutral";

  const showSkeletons = !latestId || metricsLoading;

  return (
    <div className="p-6 space-y-6 animate-fade-in">

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-foreground tracking-tight">
            {greeting}, {firstName} 👋
          </h1>
          <p className="text-base text-muted-foreground mt-1">
            {new Date().toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long", year: "numeric" })}
          </p>
        </div>
        <Link href="/upload" className="btn-primary text-base px-5 py-3">
          <Plus className="w-5 h-5" />
          New upload
        </Link>
      </div>

      {/* KPI cards — real data from latest upload */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        {showSkeletons ? (
          <>
            <MetricSkeleton variant="orange"  />
            <MetricSkeleton variant="emerald" />
            <MetricSkeleton variant="blue"    />
            <MetricSkeleton variant="purple"  />
          </>
        ) : (
          <>
            <MetricCard
              label="Revenue this period"
              value={revenue}
              change={changePct}
              trend={revTrend}
              icon={IndianRupee}
              variant="orange"
            />
            <MetricCard
              label="Top products tracked"
              value={String(metrics?.top_products?.length ?? 0)}
              change={metrics?.period_label?.split(" vs ")[0] ?? "This period"}
              trend="neutral"
              icon={Package}
              variant="emerald"
            />
            <MetricCard
              label="Dead stock items"
              value={String(metrics?.dead_stock_count ?? 0)}
              change={metrics?.dead_stock_count ? "Needs attention" : "All clear"}
              trend={metrics?.dead_stock_count ? "down" : "neutral"}
              icon={Users}
              variant="blue"
            />
            <MetricCard
              label="Data health"
              value={healthLabel}
              change={healthBadge}
              trend={healthTrend}
              icon={Star}
              variant="purple"
            />
          </>
        )}
      </div>

      {/* Revenue chart + Recent uploads */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">

        {/* Revenue trend chart */}
        <div className="xl:col-span-2 card p-6">
          <div className="flex items-start justify-between mb-6">
            <div>
              <h2 className="text-xl font-bold text-foreground">Revenue trend</h2>
              <p className="text-base text-muted-foreground mt-0.5">
                {metrics?.period_label ?? (latestId ? "Loading chart..." : "Upload a file to see your trend")}
              </p>
            </div>
            {metrics && (
              <span className={`badge text-sm px-3 py-1.5 flex items-center gap-1.5 ${
                revTrend === "up" ? "badge-up" : revTrend === "down" ? "badge-down" : "badge-neutral"
              }`}>
                {revTrend === "up"   && <TrendingUp   className="w-4 h-4" />}
                {revTrend === "down" && <TrendingDown className="w-4 h-4" />}
                {changePct}
              </span>
            )}
          </div>

          {chartData.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <AreaChart data={chartData} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
                <defs>
                  <linearGradient id="dash-rev" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor="#F97316" stopOpacity={0.2} />
                    <stop offset="95%" stopColor="#F97316" stopOpacity={0}   />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(255,255,255,0.04)" />
                <XAxis
                  dataKey="label"
                  tick={{ fontSize: 12, fill: "hsl(var(--muted-foreground))" }}
                  axisLine={false} tickLine={false}
                  interval="preserveStartEnd"
                />
                <YAxis hide />
                <Tooltip content={<CustomTooltip />} />
                <Area
                  type="monotone" dataKey="revenue"
                  stroke="#F97316" strokeWidth={2.5}
                  fill="url(#dash-rev)" dot={false}
                  activeDot={{ r: 5, fill: "#F97316" }}
                />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[220px] flex flex-col items-center justify-center text-center">
              <div className="w-14 h-14 bg-orange-500/10 rounded-2xl flex items-center justify-center mb-4">
                <Activity className="w-7 h-7 text-orange-400" />
              </div>
              <p className="text-base font-semibold text-foreground mb-1">No chart data yet</p>
              <p className="text-sm text-muted-foreground">Upload a file to see your revenue trend</p>
            </div>
          )}
        </div>

        {/* Recent uploads */}
        <div className="card flex flex-col">
          <div className="flex items-center justify-between px-6 py-4 border-b border-border">
            <h2 className="text-lg font-bold text-foreground">Recent uploads</h2>
            <Link href="/reports" className="text-sm text-orange-400 hover:text-orange-300 font-medium flex items-center gap-1">
              All <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>
          {analyses.length === 0 ? (
            <div className="flex flex-col items-center justify-center flex-1 py-12 px-6">
              <div className="w-14 h-14 bg-secondary rounded-2xl flex items-center justify-center mb-4">
                <Upload className="w-6 h-6 text-muted-foreground" />
              </div>
              <p className="text-base font-semibold text-foreground mb-1">No uploads yet</p>
              <p className="text-sm text-muted-foreground text-center mb-5">
                Upload your first file to get AI analysis
              </p>
              <Link href="/upload" className="btn-primary text-sm">Upload now</Link>
            </div>
          ) : (
            <div className="flex-1 divide-y divide-border">
              {analyses.slice(0, 5).map((a) => (
                <Link
                  key={a.upload_id}
                  href={`/analysis/${a.upload_id}`}
                  className="flex items-center gap-3 px-6 py-4 hover:bg-secondary/50 transition-colors group"
                >
                  <div className="w-10 h-10 rounded-xl bg-orange-500/15 flex items-center justify-center flex-shrink-0">
                    <FileText className="w-5 h-5 text-orange-400" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-foreground truncate">{a.file_name}</p>
                    <p className="text-xs text-muted-foreground mt-0.5">{relativeTime(a.created_at)}</p>
                  </div>
                  {a.anomaly_count > 0 && (
                    <span className="text-xs bg-red-500/15 text-red-400 px-2 py-0.5 rounded-full font-semibold flex-shrink-0">
                      {a.anomaly_count} alerts
                    </span>
                  )}
                  <ArrowRight className="w-4 h-4 text-muted-foreground/30 group-hover:text-orange-400 transition-colors flex-shrink-0" />
                </Link>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Quick actions */}
      <div className="card p-6">
        <h2 className="text-lg font-bold text-foreground mb-4">Quick actions</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[
            { label: "Upload data",  icon: Upload,         href: "/upload",  color: "text-orange-400 bg-orange-500/15" },
            { label: "View reports", icon: FileText,        href: "/reports", color: "text-blue-400 bg-blue-500/15"    },
            { label: "Check alerts", icon: AlertTriangle,   href: "/alerts",  color: "text-red-400 bg-red-500/15"      },
            { label: "Customers",    icon: Users,           href: "/reports", color: "text-purple-400 bg-purple-500/15" },
          ].map((a) => (
            <Link
              key={a.label}
              href={a.href}
              className="flex items-center gap-3 p-4 rounded-2xl border border-border hover:border-orange-500/30 hover:bg-orange-500/5 transition-all duration-150 group"
            >
              <div className={`w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 ${a.color}`}>
                <a.icon className="w-5 h-5" />
              </div>
              <span className="text-base font-medium text-muted-foreground group-hover:text-foreground transition-colors">
                {a.label}
              </span>
            </Link>
          ))}
        </div>
      </div>

    </div>
  );
}
