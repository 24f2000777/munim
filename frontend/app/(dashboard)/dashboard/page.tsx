"use client";
import { useSession } from "next-auth/react";
import { useAnalysisHistory, useAnalysisMetrics, useAnalysisAnomalies } from "@/lib/api/analysis";
import { MetricCard } from "@/components/dashboard/MetricCard";
import { RevenueChart } from "@/components/dashboard/RevenueChart";
import {
  TrendingUp, Package, Users, AlertTriangle,
  Upload, ArrowRight, Zap,
} from "lucide-react";
import { formatINR, trendSymbol, formatDate, relativeTime } from "@/lib/utils";
import Link from "next/link";
import type { Trend } from "@/lib/types";

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-24 text-center animate-fade-in">
      <div className="w-16 h-16 rounded-2xl bg-saffron/10 flex items-center justify-center mb-5">
        <Upload className="w-8 h-8 text-saffron" />
      </div>
      <h2 className="text-xl font-bold text-forest mb-2">Pehla upload karo</h2>
      <p className="text-sm text-muted-foreground max-w-xs mb-6">
        Apna Tally XML ya Excel file upload karo — Munim baaki kaam karta hai.
      </p>
      <Link
        href="/upload"
        className="inline-flex items-center gap-2 bg-saffron hover:bg-saffron-dark text-white font-semibold px-6 py-2.5 rounded-xl shadow-warm transition-all duration-200"
      >
        Upload karo <ArrowRight className="w-4 h-4" />
      </Link>
    </div>
  );
}

export default function DashboardPage() {
  const { data: session } = useSession();
  const firstName = session?.user?.name?.split(" ")[0] ?? "Vyapari";

  const { data: history, isLoading: historyLoading } = useAnalysisHistory(1, 1);
  const latestUploadId = history?.items?.[0]?.upload_id ?? "";

  const { data: metrics, isLoading: metricsLoading } = useAnalysisMetrics(latestUploadId);
  const { data: anomalies } = useAnalysisAnomalies(latestUploadId);

  const loading = historyLoading || metricsLoading;
  const hasData = !!latestUploadId;

  // Build chart data from history items
  const { data: fullHistory } = useAnalysisHistory(1, 8);
  const chartData = (fullHistory?.items ?? [])
    .slice()
    .reverse()
    .map((item) => ({
      date:    formatDate(item.period_end).slice(0, 6), // "15 Jan"
      revenue: item.current_revenue ?? 0,
    }));

  const revenue    = metrics?.revenue;
  const topProduct = metrics?.top_products?.[0];
  const deadStock  = metrics?.dead_stock_count ?? 0;
  const alertCount = (anomalies?.high_count ?? 0) + (anomalies?.medium_count ?? 0);

  if (!loading && !hasData) return <EmptyState />;

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-forest">
            Namaste, {firstName} 🙏
          </h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            {latestUploadId && history?.items?.[0]
              ? `Last updated ${relativeTime(history.items[0].created_at)}`
              : "Abhi koi data nahi hai"}
          </p>
        </div>
        <Link
          href="/upload"
          className="hidden md:inline-flex items-center gap-2 bg-saffron/10 hover:bg-saffron/20 text-saffron font-semibold text-sm px-4 py-2 rounded-xl transition-colors"
        >
          <Upload className="w-4 h-4" />
          Upload
        </Link>
      </div>

      {/* HIGH alert banner */}
      {(anomalies?.high_count ?? 0) > 0 && (
        <div className="bg-red-50 border border-red-200 rounded-2xl px-5 py-4 flex items-center gap-4 animate-fade-in">
          <div className="w-9 h-9 rounded-xl bg-red-100 flex items-center justify-center flex-shrink-0">
            <AlertTriangle className="w-5 h-5 text-red-600" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-red-700">
              {anomalies!.high_count} HIGH severity{" "}
              {anomalies!.high_count === 1 ? "alert" : "alerts"} detected
            </p>
            <p className="text-xs text-red-600 truncate">
              {anomalies?.anomalies?.[0]?.title}
            </p>
          </div>
          <Link
            href="/alerts"
            className="text-xs font-semibold text-red-600 hover:text-red-700 flex items-center gap-1 flex-shrink-0"
          >
            View <ArrowRight className="w-3 h-3" />
          </Link>
        </div>
      )}

      {/* Metric cards — 2 col mobile, 4 col desktop */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard
          label="Revenue"
          value={revenue ? formatINR(revenue.current, true) : "—"}
          trend={(revenue?.trend as Trend) ?? null}
          trendPct={revenue ? trendSymbol(revenue.change_pct) : undefined}
          sub={`vs ${revenue ? formatINR(revenue.previous, true) : "—"} last week`}
          icon={<TrendingUp className="w-4 h-4 text-saffron" />}
          accent="saffron"
          loading={loading}
        />
        <MetricCard
          label="Top Product"
          value={topProduct?.name ?? "—"}
          sub={topProduct ? formatINR(topProduct.revenue, true) : "Upload karo"}
          icon={<Zap className="w-4 h-4 text-golden-dark" />}
          accent="golden"
          loading={loading}
        />
        <MetricCard
          label="Dead Stock"
          value={loading ? "—" : `${deadStock} items`}
          sub={deadStock > 0 ? "Not sold in 14+ days" : "Sab theek hai ✅"}
          accent={deadStock > 0 ? "red" : "forest"}
          icon={<Package className="w-4 h-4 text-forest" />}
          loading={loading}
        />
        <MetricCard
          label="Alerts"
          value={loading ? "—" : `${alertCount}`}
          sub={alertCount > 0 ? "Need attention" : "All clear ✅"}
          accent={alertCount > 0 ? "red" : "forest"}
          icon={<AlertTriangle className={`w-4 h-4 ${alertCount > 0 ? "text-red-500" : "text-forest"}`} />}
          loading={loading}
        />
      </div>

      {/* Revenue chart */}
      {chartData.length > 0 && (
        <div className="bg-card border border-border rounded-2xl p-5 shadow-metric">
          <div className="flex items-center justify-between mb-5">
            <div>
              <h2 className="font-semibold text-forest">Revenue Trend</h2>
              <p className="text-xs text-muted-foreground mt-0.5">Last 8 weeks</p>
            </div>
            <Link
              href={`/analysis/${latestUploadId}`}
              className="text-xs font-semibold text-saffron hover:text-saffron-dark flex items-center gap-1"
            >
              Full analysis <ArrowRight className="w-3 h-3" />
            </Link>
          </div>
          <RevenueChart data={chartData} />
        </div>
      )}

      {/* Recent uploads */}
      {(fullHistory?.items?.length ?? 0) > 0 && (
        <div className="bg-card border border-border rounded-2xl p-5 shadow-metric">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-forest">Recent Uploads</h2>
            <Link
              href="/upload"
              className="text-xs font-semibold text-saffron hover:text-saffron-dark flex items-center gap-1"
            >
              New upload <ArrowRight className="w-3 h-3" />
            </Link>
          </div>
          <div className="space-y-2">
            {fullHistory!.items.slice(0, 4).map((item) => (
              <Link
                key={item.upload_id}
                href={`/analysis/${item.upload_id}`}
                className="flex items-center gap-3 p-3 rounded-xl hover:bg-muted/60 transition-colors group"
              >
                <div className="w-8 h-8 rounded-lg bg-saffron/10 flex items-center justify-center flex-shrink-0">
                  <Package className="w-4 h-4 text-saffron" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-foreground truncate">{item.file_name}</p>
                  <p className="text-xs text-muted-foreground">
                    {formatDate(item.period_start)} — {formatDate(item.period_end)}
                  </p>
                </div>
                <div className="text-right flex-shrink-0">
                  <p className="text-sm font-semibold text-forest">
                    {item.current_revenue ? formatINR(item.current_revenue, true) : "—"}
                  </p>
                  <p className="text-[10px] text-muted-foreground">{relativeTime(item.created_at)}</p>
                </div>
                <ArrowRight className="w-4 h-4 text-muted-foreground/40 group-hover:text-saffron transition-colors flex-shrink-0" />
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
