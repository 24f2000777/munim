"use client";
import { useAnalysisHistory, useAnalysisAnomalies } from "@/lib/api/analysis";
import { AlertTriangle, CheckCircle2, ChevronLeft } from "lucide-react";
import { cn } from "@/lib/utils";
import Link from "next/link";

export default function AlertsPage() {
  const { data: history } = useAnalysisHistory(1, 1);
  const uploadId = history?.items?.[0]?.upload_id ?? "";
  const { data: anomalies, isLoading } = useAnalysisAnomalies(uploadId);

  const BADGE = { HIGH: "badge-high", MEDIUM: "badge-medium", LOW: "badge-low" } as const;

  return (
    <div className="max-w-2xl mx-auto animate-fade-in">
      <Link href="/dashboard" className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-forest transition-colors mb-5">
        <ChevronLeft className="w-4 h-4" /> Dashboard
      </Link>

      <div className="flex items-center justify-between mb-5">
        <div>
          <h1 className="text-xl font-bold text-forest">Alerts</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Anomalies from your latest analysis</p>
        </div>
        {anomalies && (
          <div className="flex items-center gap-2">
            {anomalies.high_count   > 0 && <span className="badge-high">HIGH: {anomalies.high_count}</span>}
            {anomalies.medium_count > 0 && <span className="badge-medium">MED: {anomalies.medium_count}</span>}
            {anomalies.low_count    > 0 && <span className="badge-low">LOW: {anomalies.low_count}</span>}
          </div>
        )}
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {Array(3).fill(0).map((_, i) => <div key={i} className="skeleton h-24 rounded-2xl" />)}
        </div>
      ) : !anomalies?.anomalies?.length ? (
        <div className="text-center py-20 bg-card border border-border rounded-2xl">
          <CheckCircle2 className="w-12 h-12 text-green-500 mx-auto mb-3" />
          <p className="text-base font-bold text-forest">All clear</p>
          <p className="text-sm text-muted-foreground mt-1">No anomalies detected in your latest upload</p>
        </div>
      ) : (
        <div className="space-y-3">
          {anomalies.anomalies.map((a, i) => (
            <div
              key={i}
              className={cn(
                "bg-card border rounded-2xl p-5 shadow-metric",
                a.severity === "HIGH"   ? "border-l-4 border-l-red-500 border-red-100"    : "",
                a.severity === "MEDIUM" ? "border-l-4 border-l-amber-500 border-amber-100" : "",
                a.severity === "LOW"    ? "border-l-4 border-l-blue-400 border-blue-100"   : "",
              )}
            >
              <div className="flex items-start gap-3">
                <AlertTriangle className={cn(
                  "w-4 h-4 mt-0.5 flex-shrink-0",
                  a.severity === "HIGH"   ? "text-red-500"   : "",
                  a.severity === "MEDIUM" ? "text-amber-500" : "",
                  a.severity === "LOW"    ? "text-blue-500"  : "",
                )} />
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                    <span className="font-bold text-forest text-sm">{a.title}</span>
                    <span className={BADGE[a.severity]}>{a.severity}</span>
                  </div>
                  <p className="text-sm text-muted-foreground leading-relaxed">{a.explanation}</p>
                  {a.action && (
                    <div className="mt-3 bg-saffron/5 border border-saffron/15 rounded-xl px-3 py-2.5">
                      <p className="text-xs font-semibold text-saffron mb-0.5">Recommended action</p>
                      <p className="text-sm text-forest">{a.action}</p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
