"use client";
import { useSession } from "next-auth/react";
import { useAnalysisHistory, useAnalysisMetrics, useAnalysisAnomalies } from "@/lib/api/analysis";
import { MetricCard } from "@/components/dashboard/MetricCard";
import { RevenueChart } from "@/components/dashboard/RevenueChart";
import {
  TrendingUp, Package, AlertTriangle,
  Upload, ArrowRight, Zap,
} from "lucide-react";
import { formatINR, trendSymbol, formatDate, relativeTime } from "@/lib/utils";
import Link from "next/link";
import type { Trend } from "@/lib/types";

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-24 text-center animate-fade-in">
      <div className="w-14 h-14 rounded-2xl bg-saffron/10 flex items-center justify-center mb-4">
        <Upload className="w-7 h-7 text-saffron" />
      </div>
      <h2 className="text-xl font-bold text-forest mb-2">Upload your first file</h2>
      <p className="text-sm text-muted-foreground max-w-xs mb-6 leading-relaxed">
        Upload your Tally XML or Excel export. Munim will analyse your data and generate a business summary.
      </p>
      <Link
        href="/upload"
        className="inline-flex items-center gap-2 bg-saffron hover:bg-saffron-dark text-white font-semibold px-5 py-2.5 rounded-xl shadow-warm transition-all duration-200 text-sm"
      >
        Upload now <ArrowRight className="w-4 h-4" />
      </Link>
    </div>
  );
}

export default function DashboardPage() {
  const { data: session } = useSession();
  const firstName = session?.user?.name?.split(" ")[0] ?? "there";

  const { data: history, isLoading: historyLoading } = useAnalysisHistory(1, 1);
  const latestUploadId = history?.items?.[0]?.upload_id ?? "";

  const { data: metrics, isLoading: metricsLoading } = useAnalysisMetrics(latestUploadId);
  const { data: anomalies } = useAnalysisAnomalies(latestUploadId);

  const loading = historyLoading || metricsLoading;
  const hasData = !!latestUploadId;

  const { data: fullHistory } = useAnalysisHistory(1, 8);
  const chartData = (fullHistory?.items ?? [])
    .slice()
    .reverse()
    .map((item) => ({
      date:    formatDate(item.period_end).slice(0, 6),
      revenue: item.current_revenue ?? 0,
    }));

  const revenue    = metrics?.revenue;
  const topProduct = metrics?.top_products?.[0];
  const deadStock  = metrics?.dead_stock_count ?? 0;
  const alertCount = (anomalies?.high_count ?? 0) + (anomalies?.medium_count ?? 0);

  if (!loading && !hasData) return <EmptyState />;

  return (
    <div className="space-y-5 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-forest">
            Good {new Date().getHours() < 12 ? "morning" : "afternoon"}, {firstName}
          </h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            {latestUploadId && history?.items?.[0]
              ? `Last updated ${relativeTime(history.items[0].created_at)}`
              : "No data yet"}
          </p>
        </div>
        <Link
          href="/upload"
          className="hidden md:inline-flex items-center gap-2 bg-saffron/10 hover:bg-saffron/20 text-saffron font-semibold text-sm px-4 py-2 rounded-xl transition-colors"
        >
          <Upload className="w-4 h-4" />
          New upload
        </Link>
      </div>

      {/* HIGH alert banner */}
      {(anomalies?.high_count ?? 0) > 0 && (
        <div className="bg-red-50 border border-red-200 rounded-2xl px-4 py-3 flex items-center gap-3 animate-fade-in">
          <AlertTriangle className="w-5 h-5 text-red-500 flex-shrink-0" />
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-red-700">
              {anomalies!.high_count} high severity {anomalies!.high_count === 1 ? "alert" : "alerts"} need attention
            </p>
            <p className="text-xs text-red-600 truncate">{anomalies?.anomalies?.[0]?.title}</p>
          </div>
          <Link href="/alerts" className="text-xs font-semibold text-red-600 hover:text-red-700 flex items-center gap-1 flex-shrink-0">
            View all <ArrowRight className="w-3 h-3" />
          </Link>
        </div>
      )}

      {/* Metric cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MetricCard
          label="Revenue"
          value={revenue ? formatINR(revenue.current, true) : "—"}
          trend={(revenue?.trend as Trend) ?? null}
          trendPct={revenue ? trendSymbol(revenue.change_pct) : undefined}
          sub={`vs ${revenue ? formatINR(revenue.previous, true) : "—"} prior period`}
          icon={<TrendingUp className="w-4 h-4 text-saffron" />}
          accent="saffron"
          loading={loading}
        />
        <MetricCard
          label="Top Product"
          value={topProduct?.name ?? "—"}
          sub={topProduct ? formatINR(topProduct.revenue, true) : "Upload to see"}
          icon={<Zap className="w-4 h-4 text-golden-dark" />}
          accent="golden"
          loading={loading}
        />
        <MetricCard
          label="Dead Stock"
          value={loading ? "—" : `${deadStock} items`}
          sub={deadStock > 0 ? "Not sold in 14+ days" : "All good"}
          accent={deadStock > 0 ? "red" : "forest"}
          icon={<Package className="w-4 h-4 text-forest" />}
          loading={loading}
        />
        <MetricCard
          label="Active Alerts"
          value={loading ? "—" : `${alertCount}`}
          sub={alertCount > 0 ? "Require attention" : "Nothing flagged"}
          accent={alertCount > 0 ? "red" : "forest"}
          icon={<AlertTriangle className={`w-4 h-4 ${alertCount > 0 ? "text-red-500" : "text-forest"}`} />}
          loading={loading}
        />
      </div>

      {/* Chart + Recent in a two-column layout on large screens */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-5">
        {/* Revenue chart — takes 3 of 5 cols */}
        {chartData.length > 0 && (
          <div className="lg:col-span-3 bg-card border border-border rounded-2xl p-5 shadow-metric">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="font-semibold text-forest text-sm">Revenue Trend</h2>
                <p className="text-xs text-muted-foreground mt-0.5">Last 8 periods</p>
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

        {/* Recent uploads — takes 2 of 5 cols */}
        {(fullHistory?.items?.length ?? 0) > 0 && (
          <div className={`${chartData.length > 0 ? "lg:col-span-2" : "lg:col-span-5"} bg-card border border-border rounded-2xl p-5 shadow-metric`}>
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-semibold text-forest text-sm">Recent Uploads</h2>
              <Link href="/upload" className="text-xs font-semibold text-saffron hover:text-saffron-dark flex items-center gap-1">
                Upload <ArrowRight className="w-3 h-3" />
              </Link>
            </div>
            <div className="space-y-1">
              {fullHistory!.items.slice(0, 5).map((item) => (
                <Link
                  key={item.upload_id}
                  href={`/analysis/${item.upload_id}`}
                  className="flex items-center gap-3 p-2.5 rounded-xl hover:bg-muted/60 transition-colors group"
                >
                  <div className="w-7 h-7 rounded-lg bg-saffron/10 flex items-center justify-center flex-shrink-0">
                    <Package className="w-3.5 h-3.5 text-saffron" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-medium text-foreground truncate">{item.file_name}</p>
                    <p className="text-[10px] text-muted-foreground">{relativeTime(item.created_at)}</p>
                  </div>
                  <p className="text-xs font-semibold text-forest flex-shrink-0">
                    {item.current_revenue ? formatINR(item.current_revenue, true) : "—"}
                  </p>
                </Link>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
