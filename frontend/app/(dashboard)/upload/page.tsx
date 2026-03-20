"use client";
import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { useRouter } from "next/navigation";
import { useUploadFile, useUploadStatus } from "@/lib/api/upload";
import { ACCEPTED_FILE_TYPES, MAX_FILE_SIZE_BYTES } from "@/lib/constants";
import { cn } from "@/lib/utils";
import {
  Upload, FileText, CheckCircle2, Loader2,
  AlertCircle, ArrowRight, File,
} from "lucide-react";
import { toast } from "sonner";

type Stage = "idle" | "uploading" | "processing" | "done" | "error";

const STEPS = [
  { key: "uploading",   label: "File received",  icon: Upload       },
  { key: "processing",  label: "AI analysing",   icon: Loader2      },
  { key: "done",        label: "Report ready",   icon: CheckCircle2 },
];

function Stepper({ stage }: { stage: Stage }) {
  const stageMap: Record<string, number> = { uploading: 0, processing: 1, done: 2 };
  const stepIndex = stageMap[stage] ?? -1;
  return (
    <div className="flex items-center justify-center gap-2 my-6">
      {STEPS.map((step, i) => {
        const done    = i < stepIndex;
        const current = i === stepIndex;
        return (
          <div key={step.key} className="flex items-center gap-2">
            <div className={cn(
              "flex flex-col items-center gap-1",
            )}>
              <div className={cn(
                "w-10 h-10 rounded-xl flex items-center justify-center transition-all duration-300",
                done    ? "bg-green-100"     : "",
                current ? "bg-saffron/15"    : "",
                !done && !current ? "bg-muted" : "",
              )}>
                <step.icon className={cn(
                  "w-5 h-5",
                  done    ? "text-green-600"  : "",
                  current ? "text-saffron animate-pulse" : "",
                  !done && !current ? "text-muted-foreground" : "",
                )} />
              </div>
              <span className={cn(
                "text-[10px] font-medium text-center",
                done    ? "text-green-600"    : "",
                current ? "text-saffron"      : "text-muted-foreground",
              )}>
                {step.label}
              </span>
            </div>
            {i < STEPS.length - 1 && (
              <div className={cn(
                "w-12 h-0.5 mb-4 rounded-full transition-all duration-500",
                i < stepIndex ? "bg-green-400" : "bg-border",
              )} />
            )}
          </div>
        );
      })}
    </div>
  );
}

export default function UploadPage() {
  const router = useRouter();
  const [stage, setStage]       = useState<Stage>("idle");
  const [uploadId, setUploadId] = useState<string | null>(null);
  const [fileName, setFileName] = useState<string>("");
  const [error, setError]       = useState<string>("");

  const uploadMutation = useUploadFile();

  // Poll status only when processing
  const { data: statusData } = useUploadStatus(
    stage === "processing" || stage === "done" ? uploadId : null
  );

  // React to status changes
  if (statusData?.status === "completed" && stage === "processing") {
    setStage("done");
    setTimeout(() => {
      router.push(`/analysis/${uploadId}`);
    }, 1500);
  }
  if (statusData?.status === "failed" && stage !== "error") {
    setStage("error");
    setError(statusData.error_message ?? "Processing failed. Please try again.");
  }

  const onDrop = useCallback(
    async (acceptedFiles: File[]) => {
      const file = acceptedFiles[0];
      if (!file) return;

      if (file.size > MAX_FILE_SIZE_BYTES) {
        toast.error("File too large! Max 50 MB allowed.");
        return;
      }

      setFileName(file.name);
      setStage("uploading");
      setError("");

      try {
        const result = await uploadMutation.mutateAsync(file);
        setUploadId(result.upload_id);
        setStage("processing");
      } catch (err: any) {
        setStage("error");
        setError(err.message ?? "Upload failed");
        toast.error("Upload failed — " + (err.message ?? "try again"));
      }
    },
    [uploadMutation]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept:   ACCEPTED_FILE_TYPES,
    maxFiles: 1,
    disabled: stage !== "idle" && stage !== "error",
  });

  const reset = () => {
    setStage("idle");
    setUploadId(null);
    setFileName("");
    setError("");
  };

  return (
    <div className="max-w-2xl mx-auto animate-fade-in">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-forest">Upload karo</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Tally XML, Excel ya CSV file — Munim baaki kaam karta hai
        </p>
      </div>

      <div className="bg-card border border-border rounded-2xl shadow-metric p-6 md:p-8">
        {/* Idle / error — show dropzone */}
        {(stage === "idle" || stage === "error") && (
          <>
            <div
              {...getRootProps()}
              className={cn(
                "border-2 border-dashed rounded-2xl p-10 md:p-14 text-center transition-all duration-200 cursor-pointer",
                isDragActive
                  ? "border-saffron bg-saffron/5 scale-[1.01]"
                  : "border-border hover:border-saffron/50 hover:bg-muted/30",
              )}
            >
              <input {...getInputProps()} />
              <div className={cn(
                "w-14 h-14 rounded-2xl flex items-center justify-center mx-auto mb-4 transition-all",
                isDragActive ? "bg-saffron text-white scale-110" : "bg-muted",
              )}>
                <Upload className={cn("w-7 h-7", isDragActive ? "text-white" : "text-muted-foreground")} />
              </div>

              {isDragActive ? (
                <p className="text-saffron font-semibold text-base">
                  Chod do yahan! ✨
                </p>
              ) : (
                <>
                  <p className="font-semibold text-forest text-base mb-1">
                    File drag karo ya click karo
                  </p>
                  <p className="text-sm text-muted-foreground">
                    Tally XML, Excel (.xlsx, .xls), CSV
                  </p>
                  <p className="text-xs text-muted-foreground mt-1">Max 50 MB</p>
                </>
              )}
            </div>

            {/* Supported formats */}
            <div className="flex items-center justify-center gap-4 mt-5">
              {[
                { icon: FileText, label: "Tally XML", color: "text-saffron" },
                { icon: File,     label: "Excel",     color: "text-forest"  },
                { icon: File,     label: "CSV",       color: "text-golden-dark" },
              ].map((fmt) => (
                <div key={fmt.label} className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <fmt.icon className={`w-3.5 h-3.5 ${fmt.color}`} />
                  {fmt.label}
                </div>
              ))}
            </div>

            {error && (
              <div className="mt-4 bg-red-50 border border-red-200 rounded-xl px-4 py-3 flex items-start gap-3">
                <AlertCircle className="w-4 h-4 text-red-500 mt-0.5 flex-shrink-0" />
                <div>
                  <p className="text-sm font-semibold text-red-700">Error</p>
                  <p className="text-xs text-red-600">{error}</p>
                </div>
              </div>
            )}
          </>
        )}

        {/* Processing states */}
        {(stage === "uploading" || stage === "processing" || stage === "done") && (
          <div className="text-center py-4">
            <div className="w-14 h-14 rounded-2xl bg-saffron/10 flex items-center justify-center mx-auto mb-4">
              <FileText className="w-7 h-7 text-saffron" />
            </div>
            <p className="font-semibold text-forest text-base mb-1">{fileName}</p>
            <p className="text-xs text-muted-foreground mb-2">
              {stage === "uploading"  && "Uploading..."}
              {stage === "processing" && "AI analyse kar raha hai..."}
              {stage === "done"       && "Analysis ready! Redirect ho rahe ho..."}
            </p>

            <Stepper stage={stage} />

            {stage === "processing" && (
              <p className="text-xs text-muted-foreground mt-2">
                Isme 10–30 seconds lag sakte hain ⏳
              </p>
            )}

            {stage === "done" && (
              <div className="flex items-center justify-center gap-2 text-green-600 font-semibold text-sm mt-2">
                <CheckCircle2 className="w-4 h-4" />
                Analysis complete! Moving to results...
              </div>
            )}
          </div>
        )}
      </div>

      {/* Recent uploads link */}
      <div className="mt-4 text-center">
        <a
          href="/dashboard"
          className="text-sm text-muted-foreground hover:text-forest transition-colors inline-flex items-center gap-1"
        >
          Dashboard dekho <ArrowRight className="w-3 h-3" />
        </a>
      </div>

      {/* Instructions */}
      <div className="mt-6 bg-forest/5 border border-forest/10 rounded-2xl p-5">
        <h3 className="font-semibold text-forest text-sm mb-3">Kaise export karein Tally se?</h3>
        <ol className="space-y-2 text-sm text-muted-foreground">
          <li className="flex gap-2"><span className="font-bold text-forest">1.</span> TallyPrime mein Gateway of Tally kholein</li>
          <li className="flex gap-2"><span className="font-bold text-forest">2.</span> Display → Reports → Statement of Accounts</li>
          <li className="flex gap-2"><span className="font-bold text-forest">3.</span> Export → XML format select karein</li>
          <li className="flex gap-2"><span className="font-bold text-forest">4.</span> Save karein aur yahan upload karein</li>
        </ol>
      </div>
    </div>
  );
}
