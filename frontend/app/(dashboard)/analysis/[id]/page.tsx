"use client";
import { use, useState } from "react";
import { useAnalysisMetrics, useAnalysisAnomalies, useAnalysisCustomers } from "@/lib/api/analysis";
import { formatINR, trendSymbol, formatDate } from "@/lib/utils";
import { SEGMENT_COLORS, SEVERITY_COLORS } from "@/lib/constants";
import {
  TrendingUp, TrendingDown, Package, AlertTriangle,
  Users, ChevronLeft, CheckCircle2,
} from "lucide-react";
import { cn } from "@/lib/utils";
import Link from "next/link";
import type { Trend } from "@/lib/types";

// ── Simple tabs without Radix ─────────────────────────────────────────
function Tabs({
  tabs,
  active,
  onChange,
}: {
  tabs: { key: string; label: string; count?: number }[];
  active: string;
  onChange: (key: string) => void;
}) {
  return (
    <div className="flex gap-1 bg-muted/50 p-1 rounded-xl overflow-x-auto">
      {tabs.map((tab) => (
        <button
          key={tab.key}
          onClick={() => onChange(tab.key)}
          className={cn(
            "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium whitespace-nowrap transition-all",
            active === tab.key
              ? "bg-card text-forest shadow-sm"
              : "text-muted-foreground hover:text-forest"
          )}
        >
          {tab.label}
          {tab.count !== undefined && (
            <span className={cn(
              "text-xs rounded-full px-1.5 py-0.5 font-semibold",
              active === tab.key ? "bg-saffron/15 text-saffron" : "bg-border text-muted-foreground",
            )}>
              {tab.count}
            </span>
          )}
        </button>
      ))}
    </div>
  );
}

// ── Skeleton loader ──────────────────────────────────────────────────
function SkeletonBlock({ h = "h-4", w = "w-full" }: { h?: string; w?: string }) {
  return <div className={cn("skeleton", h, w)} />;
}

// ── Overview Tab ─────────────────────────────────────────────────────
function OverviewTab({ uploadId }: { uploadId: string }) {
  const { data, isLoading } = useAnalysisMetrics(uploadId);
  if (isLoading) return (
    <div className="space-y-4">
      <SkeletonBlock h="h-20" />
      <div className="grid grid-cols-2 gap-4">
        <SkeletonBlock h="h-24" />
        <SkeletonBlock h="h-24" />
      </div>
    </div>
  );
  if (!data) return <p className="text-sm text-muted-foreground">No data available</p>;

  const { revenue } = data;
  const isUp = revenue.trend === "up";

  return (
    <div className="space-y-4">
      {/* Period */}
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <span>{formatDate(data.period_start)}</span>
        <span>→</span>
        <span>{formatDate(data.period_end)}</span>
      </div>

      {/* Revenue card */}
      <div className={cn(
        "rounded-2xl p-5 border",
        isUp ? "bg-green-50 border-green-200" : "bg-red-50 border-red-200",
      )}>
        <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
          Period Revenue
        </p>
        <div className="flex items-end gap-3 flex-wrap">
          <span className="text-3xl md:text-4xl font-black text-forest">
            {formatINR(revenue.current)}
          </span>
          <span className={cn(
            "inline-flex items-center gap-1 text-sm font-semibold px-2.5 py-1 rounded-full mb-1",
            isUp ? "text-green-700 bg-green-100" : "text-red-700 bg-red-100",
          )}>
            {isUp ? <TrendingUp className="w-3.5 h-3.5" /> : <TrendingDown className="w-3.5 h-3.5" />}
            {trendSymbol(revenue.change_pct)}
          </span>
        </div>
        <p className="text-sm text-muted-foreground mt-1">
          Previous period: {formatINR(revenue.previous)}
        </p>
      </div>

      {/* Dead stock */}
      {data.dead_stock.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-2xl p-4">
          <div className="flex items-center gap-2 mb-3">
            <Package className="w-4 h-4 text-amber-600" />
            <p className="text-sm font-semibold text-amber-700">
              {data.dead_stock_count} Dead Stock items
            </p>
          </div>
          <div className="space-y-2">
            {data.dead_stock.slice(0, 3).map((item, i) => (
              <div key={i} className="flex items-center justify-between text-sm">
                <span className="text-amber-800 font-medium">{item.product}</span>
                <span className="text-amber-600 text-xs font-semibold">
                  {item.days_since_last_sale} days
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Products Tab ─────────────────────────────────────────────────────
function ProductsTab({ uploadId }: { uploadId: string }) {
  const { data, isLoading } = useAnalysisMetrics(uploadId);
  if (isLoading) return <div className="space-y-3">{Array(5).fill(0).map((_, i) => <SkeletonBlock key={i} h="h-12" />)}</div>;
  if (!data?.top_products?.length) return <p className="text-sm text-muted-foreground">No product data</p>;

  const maxRev = data.top_products[0].revenue;

  return (
    <div className="space-y-3">
      {data.top_products.map((p, i) => (
        <div key={i} className="bg-card border border-border rounded-xl p-4">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-3">
              <span className="w-6 h-6 rounded-lg bg-saffron/10 flex items-center justify-center text-xs font-black text-saffron">
                {i + 1}
              </span>
              <span className="font-medium text-forest text-sm">{p.name}</span>
            </div>
            <span className="font-bold text-sm text-forest">{formatINR(p.revenue, true)}</span>
          </div>
          {/* Bar */}
          <div className="h-1.5 bg-muted rounded-full overflow-hidden">
            <div
              className="h-full bg-saffron rounded-full transition-all duration-500"
              style={{ width: `${(p.revenue / maxRev) * 100}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Customers Tab ─────────────────────────────────────────────────────
function CustomersTab({ uploadId }: { uploadId: string }) {
  const { data, isLoading } = useAnalysisCustomers(uploadId);
  if (isLoading) return <div className="space-y-3">{Array(3).fill(0).map((_, i) => <SkeletonBlock key={i} h="h-12" />)}</div>;
  if (!data) return <p className="text-sm text-muted-foreground">No customer data</p>;

  const segments = Object.entries(data.segments).filter(([, v]) => v && v > 0);

  return (
    <div className="space-y-4">
      {/* Total */}
      <div className="bg-forest/5 border border-forest/15 rounded-2xl px-5 py-4">
        <p className="text-xs text-muted-foreground uppercase tracking-wider font-semibold">Total Customers</p>
        <p className="text-3xl font-black text-forest mt-1">{data.total_customers}</p>
      </div>

      {/* Segments */}
      {segments.length > 0 && (
        <div className="grid grid-cols-2 gap-3">
          {segments.map(([seg, count]) => (
            <div
              key={seg}
              className="border border-border rounded-xl px-4 py-3 bg-card"
              style={{ borderLeftColor: SEGMENT_COLORS[seg] ?? "#E8651A", borderLeftWidth: 3 }}
            >
              <p className="text-xs font-semibold text-muted-foreground capitalize">{seg.replace("_", " ")}</p>
              <p className="text-xl font-bold text-forest mt-0.5">{count}</p>
            </div>
          ))}
        </div>
      )}

      {/* Top customers */}
      {data.top_customers.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Top Customers</p>
          <div className="space-y-2">
            {data.top_customers.slice(0, 5).map((c, i) => (
              <div key={i} className="flex items-center justify-between py-2.5 px-3 rounded-xl hover:bg-muted/50 transition-colors">
                <div className="flex items-center gap-3">
                  <div className="w-7 h-7 rounded-full bg-saffron/10 flex items-center justify-center text-xs font-bold text-saffron">
                    {c.name.slice(0, 1).toUpperCase()}
                  </div>
                  <span className="text-sm font-medium text-forest truncate max-w-[160px]">{c.name}</span>
                </div>
                <span className="text-sm font-semibold text-muted-foreground">{formatINR(c.revenue, true)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Anomalies Tab ─────────────────────────────────────────────────────
function AnomaliesTab({ uploadId }: { uploadId: string }) {
  const { data, isLoading } = useAnalysisAnomalies(uploadId);
  if (isLoading) return <div className="space-y-3">{Array(3).fill(0).map((_, i) => <SkeletonBlock key={i} h="h-20" />)}</div>;
  if (!data?.anomalies?.length) {
    return (
      <div className="text-center py-10">
        <CheckCircle2 className="w-12 h-12 text-green-500 mx-auto mb-3" />
        <p className="font-semibold text-forest">Sab theek hai! 🎉</p>
        <p className="text-sm text-muted-foreground mt-1">No anomalies detected this period</p>
      </div>
    );
  }

  const BADGE = { HIGH: "badge-high", MEDIUM: "badge-medium", LOW: "badge-low" } as const;

  return (
    <div className="space-y-3">
      {/* Summary row */}
      <div className="flex gap-3 flex-wrap">
        {data.high_count > 0   && <span className="badge-high">HIGH: {data.high_count}</span>}
        {data.medium_count > 0 && <span className="badge-medium">MEDIUM: {data.medium_count}</span>}
        {data.low_count > 0    && <span className="badge-low">LOW: {data.low_count}</span>}
      </div>

      {data.anomalies.map((a, i) => (
        <div
          key={i}
          className={cn(
            "bg-card border rounded-2xl p-4",
            a.severity === "HIGH"   ? "border-red-200"    : "",
            a.severity === "MEDIUM" ? "border-amber-200"  : "",
            a.severity === "LOW"    ? "border-blue-200"   : "",
          )}
        >
          <div className="flex items-start gap-3">
            <AlertTriangle
              className={cn(
                "w-4 h-4 mt-0.5 flex-shrink-0",
                a.severity === "HIGH"   ? "text-red-500"    : "",
                a.severity === "MEDIUM" ? "text-amber-500"  : "",
                a.severity === "LOW"    ? "text-blue-500"   : "",
              )}
            />
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1 flex-wrap">
                <p className="font-semibold text-sm text-forest">{a.title}</p>
                <span className={BADGE[a.severity]}>{a.severity}</span>
              </div>
              <p className="text-sm text-muted-foreground leading-relaxed">{a.explanation}</p>
              {a.action && (
                <p className="text-xs font-semibold text-saffron mt-2">
                  → {a.action}
                </p>
              )}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────
type Params = Promise<{ id: string }>;

export default function AnalysisPage({ params }: { params: Params }) {
  const { id: uploadId } = use(params);
  const [activeTab, setActiveTab] = useState("overview");

  const { data: metrics }   = useAnalysisMetrics(uploadId);
  const { data: anomalies } = useAnalysisAnomalies(uploadId);

  const TABS = [
    { key: "overview",   label: "Overview"   },
    { key: "products",   label: "Products",  count: metrics?.top_products?.length     },
    { key: "customers",  label: "Customers"  },
    { key: "anomalies",  label: "Alerts",    count: anomalies?.total_detected          },
  ];

  return (
    <div className="max-w-2xl mx-auto animate-fade-in">
      {/* Back */}
      <Link
        href="/dashboard"
        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-forest transition-colors mb-5"
      >
        <ChevronLeft className="w-4 h-4" />
        Dashboard
      </Link>

      {/* Header */}
      <div className="flex items-start justify-between gap-4 mb-6">
        <div>
          <h1 className="text-xl font-bold text-forest">Analysis</h1>
          {metrics && (
            <p className="text-xs text-muted-foreground mt-0.5">
              {formatDate(metrics.period_start)} — {formatDate(metrics.period_end)}
            </p>
          )}
        </div>
        <Link
          href="/reports"
          className="inline-flex items-center gap-1.5 bg-saffron/10 hover:bg-saffron/20 text-saffron text-xs font-semibold px-3 py-2 rounded-xl transition-colors flex-shrink-0"
        >
          Generate Report
        </Link>
      </div>

      {/* Tabs */}
      <Tabs tabs={TABS} active={activeTab} onChange={setActiveTab} />

      {/* Tab content */}
      <div className="mt-5">
        {activeTab === "overview"  && <OverviewTab  uploadId={uploadId} />}
        {activeTab === "products"  && <ProductsTab  uploadId={uploadId} />}
        {activeTab === "customers" && <CustomersTab uploadId={uploadId} />}
        {activeTab === "anomalies" && <AnomaliesTab uploadId={uploadId} />}
      </div>
    </div>
  );
}

