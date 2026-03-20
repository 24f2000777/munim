"use client";
import { useState } from "react";
import { useReports, useGenerateReport, useSendReportWhatsApp } from "@/lib/api/reports";
import { useAnalysisHistory } from "@/lib/api/analysis";
import { formatDate, relativeTime } from "@/lib/utils";
import {
  FileText, Send, Plus, CheckCircle2,
  Loader2, MessageCircle, X,
} from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import type { Language, ReportType, Report } from "@/lib/types";

function GenerateDialog({ onClose }: { onClose: () => void }) {
  const [uploadId,   setUploadId]   = useState("");
  const [language,   setLanguage]   = useState<Language>("hi");
  const [reportType, setReportType] = useState<ReportType>("on_demand");

  const { data: history } = useAnalysisHistory(1, 10);
  const generateMutation  = useGenerateReport();

  const handleGenerate = async () => {
    if (!uploadId) { toast.error("Please select an analysis first"); return; }
    try {
      await generateMutation.mutateAsync({ upload_id: uploadId, language, report_type: reportType });
      toast.success("Report generated successfully");
      onClose();
    } catch (e: any) {
      toast.error(e.message ?? "Failed to generate report");
    }
  };

  return (
    <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-card border border-border rounded-2xl shadow-[0_32px_64px_rgba(0,0,0,0.15)] w-full max-w-md animate-fade-in">
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <h2 className="font-bold text-forest text-sm">Generate Report</h2>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-muted transition-colors">
            <X className="w-4 h-4 text-muted-foreground" />
          </button>
        </div>
        <div className="px-5 py-4 space-y-4">
          <div>
            <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1.5 block">
              Select Analysis
            </label>
            <select
              value={uploadId}
              onChange={(e) => setUploadId(e.target.value)}
              className="w-full border border-border rounded-xl px-3 py-2.5 text-sm text-forest bg-card focus:outline-none focus:ring-2 focus:ring-saffron/30"
            >
              <option value="">Select an analysis period</option>
              {history?.items?.map((item) => (
                <option key={item.upload_id} value={item.upload_id}>
                  {item.file_name} ({formatDate(item.period_end)})
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1.5 block">
              Language
            </label>
            <div className="flex gap-2">
              {(["hi", "en", "hinglish"] as Language[]).map((lang) => (
                <button
                  key={lang}
                  onClick={() => setLanguage(lang)}
                  className={cn(
                    "flex-1 py-2 rounded-xl text-xs font-semibold border transition-all",
                    language === lang
                      ? "bg-saffron/10 border-saffron/30 text-saffron"
                      : "border-border text-muted-foreground hover:border-saffron/20",
                  )}
                >
                  {lang === "hi" ? "Hindi" : lang === "en" ? "English" : "Hinglish"}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1.5 block">
              Report Type
            </label>
            <div className="grid grid-cols-2 gap-2">
              {([
                { key: "on_demand", label: "On Demand" },
                { key: "weekly",    label: "Weekly"    },
                { key: "monthly",   label: "Monthly"   },
                { key: "alert",     label: "Alert"     },
              ] as { key: ReportType; label: string }[]).map((t) => (
                <button
                  key={t.key}
                  onClick={() => setReportType(t.key)}
                  className={cn(
                    "py-2 rounded-xl text-xs font-semibold border transition-all",
                    reportType === t.key
                      ? "bg-forest/10 border-forest/30 text-forest"
                      : "border-border text-muted-foreground hover:border-forest/20",
                  )}
                >
                  {t.label}
                </button>
              ))}
            </div>
          </div>
        </div>
        <div className="px-5 pb-5">
          <button
            onClick={handleGenerate}
            disabled={generateMutation.isPending || !uploadId}
            className="w-full flex items-center justify-center gap-2 bg-saffron hover:bg-saffron-dark disabled:opacity-50 text-white font-semibold py-2.5 rounded-xl text-sm transition-all"
          >
            {generateMutation.isPending ? (
              <><Loader2 className="w-4 h-4 animate-spin" /> Generating...</>
            ) : (
              <><FileText className="w-4 h-4" /> Generate Report</>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

function SendDialog({ report, onClose }: { report: Report; onClose: () => void }) {
  const [phone, setPhone] = useState("");
  const sendMutation = useSendReportWhatsApp();

  const handleSend = async () => {
    const normalized = phone.startsWith("+") ? phone : `+91${phone}`;
    if (!/^\+\d{10,15}$/.test(normalized)) {
      toast.error("Enter a valid phone number, e.g. 9876543210");
      return;
    }
    try {
      await sendMutation.mutateAsync({ reportId: report.report_id, phone_number: normalized });
      toast.success("Sent to WhatsApp successfully");
      onClose();
    } catch (e: any) {
      toast.error(e.message ?? "Send failed");
    }
  };

  return (
    <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-card border border-border rounded-2xl shadow-[0_32px_64px_rgba(0,0,0,0.15)] w-full max-w-sm animate-fade-in">
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <div className="flex items-center gap-2">
            <MessageCircle className="w-4 h-4 text-green-600" />
            <h2 className="font-bold text-forest text-sm">Send to WhatsApp</h2>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-muted transition-colors">
            <X className="w-4 h-4 text-muted-foreground" />
          </button>
        </div>
        <div className="px-5 py-4 space-y-4">
          <p className="text-xs text-muted-foreground">
            Report: <span className="font-semibold text-forest capitalize">{report.report_type.replace("_", " ")}</span> in <span className="font-semibold text-forest uppercase">{report.language}</span>
          </p>
          <div>
            <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1.5 block">
              Phone Number
            </label>
            <div className="flex items-center border border-border rounded-xl overflow-hidden focus-within:ring-2 focus-within:ring-saffron/30">
              <span className="px-3 py-2.5 bg-muted text-sm font-semibold text-muted-foreground border-r border-border">+91</span>
              <input
                type="tel"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="9876543210"
                className="flex-1 px-3 py-2.5 text-sm text-forest bg-card focus:outline-none"
              />
            </div>
          </div>
        </div>
        <div className="px-5 pb-5">
          <button
            onClick={handleSend}
            disabled={sendMutation.isPending || !phone}
            className="w-full flex items-center justify-center gap-2 bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white font-semibold py-2.5 rounded-xl text-sm transition-all"
          >
            {sendMutation.isPending ? (
              <><Loader2 className="w-4 h-4 animate-spin" /> Sending...</>
            ) : (
              <><Send className="w-4 h-4" /> Send via WhatsApp</>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function ReportsPage() {
  const [showGenerate, setShowGenerate] = useState(false);
  const [sendingReport, setSendingReport] = useState<Report | null>(null);
  const { data, isLoading } = useReports();

  return (
    <div className="max-w-4xl mx-auto animate-fade-in">
      {showGenerate  && <GenerateDialog onClose={() => setShowGenerate(false)} />}
      {sendingReport && <SendDialog report={sendingReport} onClose={() => setSendingReport(null)} />}

      <div className="flex items-center justify-between mb-5">
        <div>
          <h1 className="text-xl font-bold text-forest">Reports</h1>
          <p className="text-sm text-muted-foreground mt-0.5">AI-generated WhatsApp reports. Up to 5 per day.</p>
        </div>
        <button
          onClick={() => setShowGenerate(true)}
          className="inline-flex items-center gap-2 bg-saffron hover:bg-saffron-dark text-white font-semibold text-sm px-4 py-2 rounded-xl shadow-warm transition-all"
        >
          <Plus className="w-4 h-4" />
          Generate
        </button>
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {Array(3).fill(0).map((_, i) => <div key={i} className="skeleton h-20 rounded-2xl" />)}
        </div>
      ) : !data?.items?.length ? (
        <div className="text-center py-20 bg-card border border-border rounded-2xl">
          <FileText className="w-10 h-10 text-muted-foreground/30 mx-auto mb-3" />
          <p className="font-semibold text-forest">No reports yet</p>
          <p className="text-sm text-muted-foreground mt-1 mb-5">Generate your first AI report</p>
          <button
            onClick={() => setShowGenerate(true)}
            className="inline-flex items-center gap-2 bg-saffron/10 hover:bg-saffron/20 text-saffron font-semibold text-sm px-4 py-2 rounded-xl transition-colors"
          >
            <Plus className="w-4 h-4" /> Generate Report
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          {data.items.map((report) => (
            <div
              key={report.report_id}
              className="bg-card border border-border rounded-2xl p-4 shadow-metric hover:shadow-warm transition-all duration-200"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-start gap-3 flex-1 min-w-0">
                  <div className="w-9 h-9 rounded-xl bg-saffron/10 flex items-center justify-center flex-shrink-0">
                    <FileText className="w-4 h-4 text-saffron" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap mb-0.5">
                      <span className="text-sm font-semibold text-forest capitalize">
                        {report.report_type.replace("_", " ")} Report
                      </span>
                      <span className="text-xs bg-muted text-muted-foreground px-2 py-0.5 rounded-full font-medium">
                        {report.language.toUpperCase()}
                      </span>
                      {report.whatsapp_sent && (
                        <span className="text-xs bg-green-50 text-green-700 border border-green-200 px-2 py-0.5 rounded-full font-medium flex items-center gap-1">
                          <CheckCircle2 className="w-3 h-3" /> Sent
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-muted-foreground">
                      {formatDate(report.period_start)} to {formatDate(report.period_end)}
                      {" · "}{relativeTime(report.created_at)} · {report.word_count} words
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => setSendingReport(report)}
                  className="p-2 rounded-lg bg-green-50 hover:bg-green-100 text-green-600 transition-colors flex-shrink-0"
                  title="Send to WhatsApp"
                >
                  <Send className="w-4 h-4" />
                </button>
              </div>

              {report.content && (
                <div className="mt-3 bg-muted/40 border border-border/60 rounded-xl px-4 py-2.5">
                  <p className="text-xs text-muted-foreground line-clamp-2 leading-relaxed">
                    {report.content.slice(0, 200)}...
                  </p>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
