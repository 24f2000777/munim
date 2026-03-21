"use client";
import { CheckCircle, TrendingDown, Package, Info, Zap, AlertTriangle } from "lucide-react";
import { useAnalysisHistory, useAnalysisAnomalies } from "@/lib/api/analysis";
import { relativeTime } from "@/lib/utils";
import type { Severity } from "@/lib/types";
import Link from "next/link";

const SEV = {
  HIGH:   { border: "border-l-red-500",   bg: "bg-red-500/10",    icon: "text-red-400",          badge: "bg-red-500/15 text-red-400"    },
  MEDIUM: { border: "border-l-amber-500", bg: "bg-amber-500/10",  icon: "text-amber-400",        badge: "bg-amber-500/15 text-amber-400" },
  LOW:    { border: "border-l-slate-500", bg: "bg-secondary",     icon: "text-muted-foreground", badge: "bg-secondary text-muted-foreground" },
};

function severityIcon(sev: Severity) {
  if (sev === "HIGH")   return TrendingDown;
  if (sev === "MEDIUM") return Package;
  return Info;
}

export default function AlertsPage() {
  // Fetch recent uploads to find the one with the most alerts
  const { data: history, isLoading: histLoading } = useAnalysisHistory(1, 5);
  const analyses = history?.items ?? [];

  // Prefer the most recent upload that has anomalies, else fall back to the latest
  const targetUpload = analyses.find((a) => a.anomaly_count > 0) ?? analyses[0];
  const uploadId     = targetUpload?.upload_id ?? "";

  const { data: anomalyData, isLoading: alertLoading } = useAnalysisAnomalies(uploadId);
  const anomalies   = anomalyData?.anomalies ?? [];
  const highCount   = anomalyData?.high_count   ?? 0;
  const mediumCount = anomalyData?.medium_count  ?? 0;
  const lowCount    = anomalyData?.low_count     ?? 0;

  const isLoading = histLoading || (!!uploadId && alertLoading);

  return (
    <div className="p-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="page-title">Alerts</h1>
          <p className="page-subtitle">
            {targetUpload
              ? `From ${targetUpload.file_name} · ${relativeTime(targetUpload.created_at)}`
              : "Anomalies and issues detected in your data"}
          </p>
        </div>
        {(highCount > 0 || mediumCount > 0 || lowCount > 0) && (
          <div className="flex items-center gap-2 flex-wrap">
            {highCount   > 0 && <span className="badge badge-high   text-sm px-3 py-1.5">{highCount}   High</span>}
            {mediumCount > 0 && <span className="badge badge-medium text-sm px-3 py-1.5">{mediumCount} Medium</span>}
            {lowCount    > 0 && <span className="badge badge-neutral text-sm px-3 py-1.5">{lowCount}    Low</span>}
          </div>
        )}
      </div>

      {/* File selector — links to other uploads */}
      {analyses.length > 1 && (
        <div className="flex gap-2 mb-5 flex-wrap">
          {analyses.map((a) => (
            <span
              key={a.upload_id}
              className={`text-sm px-3 py-1.5 rounded-full border font-medium transition-colors ${
                a.upload_id === uploadId
                  ? "border-orange-500 text-orange-400 bg-orange-500/10"
                  : "border-border text-muted-foreground"
              }`}
            >
              {a.file_name.length > 20 ? a.file_name.slice(0, 20) + "…" : a.file_name}
              {a.anomaly_count > 0 && (
                <span className="ml-1.5 bg-red-500/20 text-red-400 text-xs px-1.5 py-0.5 rounded-full">
                  {a.anomaly_count}
                </span>
              )}
            </span>
          ))}
        </div>
      )}

      {/* Loading skeletons */}
      {isLoading ? (
        <div className="space-y-3">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="card border-l-4 border-l-border p-6 animate-pulse">
              <div className="flex gap-5">
                <div className="w-12 h-12 rounded-2xl bg-secondary flex-shrink-0" />
                <div className="flex-1 space-y-3">
                  <div className="h-5 bg-secondary rounded w-2/3" />
                  <div className="h-4 bg-secondary rounded w-full" />
                  <div className="h-4 bg-secondary rounded w-4/5" />
                </div>
              </div>
            </div>
          ))}
        </div>

      /* No uploads at all */
      ) : analyses.length === 0 ? (
        <div className="card flex flex-col items-center justify-center py-24">
          <div className="w-16 h-16 bg-orange-500/15 rounded-3xl flex items-center justify-center mb-5">
            <AlertTriangle className="w-8 h-8 text-orange-400" />
          </div>
          <h3 className="text-xl font-bold text-foreground mb-2">No data yet</h3>
          <p className="text-base text-muted-foreground mb-6">Upload a file to start monitoring alerts.</p>
          <Link href="/upload" className="btn-primary">Upload now</Link>
        </div>

      /* No anomalies for this upload */
      ) : anomalies.length === 0 ? (
        <div className="card flex flex-col items-center justify-center py-24">
          <div className="w-16 h-16 bg-emerald-500/15 rounded-3xl flex items-center justify-center mb-5">
            <CheckCircle className="w-8 h-8 text-emerald-400" />
          </div>
          <h3 className="text-xl font-bold text-foreground mb-2">All clear</h3>
          <p className="text-base text-muted-foreground">No anomalies detected in your recent data.</p>
        </div>

      /* Alert cards */
      ) : (
        <div className="space-y-3">
          {anomalies.map((alert, idx) => {
            const s    = SEV[alert.severity];
            const Icon = severityIcon(alert.severity);
            return (
              <div key={idx} className={`card border-l-4 ${s.border} overflow-hidden`}>
                <div className="p-6 flex items-start gap-5">
                  <div className={`w-12 h-12 rounded-2xl flex items-center justify-center flex-shrink-0 ${s.bg}`}>
                    <Icon className={`w-6 h-6 ${s.icon}`} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 mb-2 flex-wrap">
                      <p className="text-lg font-bold text-foreground">{alert.title}</p>
                      <span className={`badge text-sm px-3 py-1 ${s.badge}`}>{alert.severity}</span>
                    </div>
                    <p className="text-base text-muted-foreground leading-relaxed mb-3">
                      {alert.explanation}
                    </p>
                    {alert.action && (
                      <div className="flex items-start gap-2 bg-secondary/60 rounded-xl px-4 py-3">
                        <Zap className="w-4 h-4 text-orange-400 flex-shrink-0 mt-0.5" />
                        <p className="text-sm text-foreground font-medium">{alert.action}</p>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
