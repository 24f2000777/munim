"use client";
import { FileText, Calendar, ArrowRight, Plus, Upload, TrendingUp } from "lucide-react";
import { useAnalysisHistory } from "@/lib/api/analysis";
import { formatINR, relativeTime } from "@/lib/utils";
import type { AnalysisHistoryItem } from "@/lib/types";
import Link from "next/link";

export default function ReportsPage() {
  const { data: history, isLoading } = useAnalysisHistory(1, 20);
  const analyses: AnalysisHistoryItem[] = history?.items ?? [];

  return (
    <div className="p-6 animate-fade-in">
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="page-title">Reports</h1>
          <p className="page-subtitle">AI analysis reports from your uploaded data</p>
        </div>
        <Link href="/upload" className="btn-primary text-base px-5 py-3">
          <Plus className="w-5 h-5" />
          New upload
        </Link>
      </div>

      {/* Loading skeletons */}
      {isLoading ? (
        <div className="space-y-3">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="card p-5 flex items-center gap-5 animate-pulse">
              <div className="w-12 h-12 rounded-2xl bg-secondary flex-shrink-0" />
              <div className="flex-1 space-y-2">
                <div className="h-5 bg-secondary rounded w-1/2" />
                <div className="h-4 bg-secondary rounded w-1/3" />
              </div>
              <div className="hidden sm:block space-y-2 text-right">
                <div className="h-5 bg-secondary rounded w-24" />
                <div className="h-4 bg-secondary rounded w-16" />
              </div>
            </div>
          ))}
        </div>

      ) : analyses.length === 0 ? (
        <div className="card flex flex-col items-center justify-center py-24 px-6">
          <div className="w-16 h-16 bg-secondary rounded-3xl flex items-center justify-center mb-5">
            <FileText className="w-8 h-8 text-muted-foreground" />
          </div>
          <h3 className="text-xl font-bold text-foreground mb-2">No reports yet</h3>
          <p className="text-base text-muted-foreground text-center max-w-xs mb-8">
            Upload your sales data to generate your first AI analysis report.
          </p>
          <Link href="/upload" className="btn-primary text-base px-6 py-3">
            <Upload className="w-5 h-5" /> Upload data
          </Link>
        </div>

      ) : (
        <div className="space-y-3">
          {analyses.map((a) => (
            <Link
              key={a.upload_id}
              href={`/analysis/${a.upload_id}`}
              className="card p-5 flex items-center gap-5 hover:border-orange-500/20 transition-all duration-150 group"
            >
              <div className="w-12 h-12 bg-orange-500/15 rounded-2xl flex items-center justify-center flex-shrink-0">
                <FileText className="w-6 h-6 text-orange-400" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-3 mb-1.5 flex-wrap">
                  <p className="text-base font-bold text-foreground truncate">{a.file_name}</p>
                  {a.file_type && (
                    <span className="badge badge-neutral">{a.file_type.toUpperCase()}</span>
                  )}
                  {a.anomaly_count > 0 && (
                    <span className="badge badge-high">{a.anomaly_count} alerts</span>
                  )}
                </div>
                <div className="flex items-center gap-4 text-sm text-muted-foreground flex-wrap">
                  <span className="flex items-center gap-1.5">
                    <Calendar className="w-3.5 h-3.5" />
                    {relativeTime(a.created_at)}
                  </span>
                  {a.period_start && (
                    <span>
                      {a.period_start.slice(0, 10)} to {a.period_end?.slice(0, 10)}
                    </span>
                  )}
                </div>
              </div>
              <div className="text-right flex-shrink-0 hidden sm:block">
                {a.current_revenue != null && (
                  <div className="flex items-center gap-1.5 text-emerald-400 text-lg font-bold mb-1">
                    <TrendingUp className="w-4 h-4" />
                    {formatINR(a.current_revenue)}
                  </div>
                )}
                {a.health_score != null && (
                  <p className="text-sm text-muted-foreground">Health: {a.health_score}/100</p>
                )}
              </div>
              <ArrowRight className="w-5 h-5 text-muted-foreground/30 group-hover:text-orange-400 transition-colors flex-shrink-0" />
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
