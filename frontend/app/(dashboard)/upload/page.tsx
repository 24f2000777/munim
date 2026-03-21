"use client";
import { useCallback, useEffect, useState } from "react";
import { useDropzone } from "react-dropzone";
import { useRouter } from "next/navigation";
import Link from "next/link";
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
  { key: "uploading",  label: "File received", icon: Upload       },
  { key: "processing", label: "AI analysing",  icon: Loader2      },
  { key: "done",       label: "Report ready",  icon: CheckCircle2 },
];

function Stepper({ stage }: { stage: Stage }) {
  const stageMap: Record<string, number> = { uploading: 0, processing: 1, done: 2 };
  const stepIndex = stageMap[stage] ?? -1;
  return (
    <div className="flex items-center justify-center gap-3 my-6">
      {STEPS.map((step, i) => {
        const done    = i < stepIndex;
        const current = i === stepIndex;
        return (
          <div key={step.key} className="flex items-center gap-3">
            <div className="flex flex-col items-center gap-1.5">
              <div className={cn(
                "w-9 h-9 rounded-xl flex items-center justify-center transition-all duration-300",
                done    ? "bg-green-500/20"    : "",
                current ? "bg-orange-500/15"   : "",
                !done && !current ? "bg-secondary" : "",
              )}>
                <step.icon className={cn(
                  "w-4 h-4",
                  done    ? "text-green-400"    : "",
                  current ? "text-orange-400 animate-pulse" : "",
                  !done && !current ? "text-muted-foreground" : "",
                )} />
              </div>
              <span className={cn(
                "text-[10px] font-medium",
                done    ? "text-green-400"  : "",
                current ? "text-orange-400" : "text-muted-foreground",
              )}>
                {step.label}
              </span>
            </div>
            {i < STEPS.length - 1 && (
              <div className={cn(
                "w-10 h-0.5 mb-4 rounded-full transition-all duration-500",
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

  const { data: statusData } = useUploadStatus(
    stage === "processing" || stage === "done" ? uploadId : null
  );

  useEffect(() => {
    if (statusData?.status === "done" && stage === "processing") {
      setStage("done");
      toast.success("Analysis complete! Opening your report...");
      setTimeout(() => {
        router.push(`/analysis/${uploadId}`);
      }, 1500);
    }
    if (statusData?.status === "error" && stage !== "error") {
      setStage("error");
      setError(statusData.error_message ?? "Processing failed. Please try again.");
      toast.error("Processing failed. Please try again.");
    }
  }, [statusData?.status, statusData?.analysis_id]);

  const onDrop = useCallback(
    async (acceptedFiles: File[]) => {
      const file = acceptedFiles[0];
      if (!file) return;
      if (file.size > MAX_FILE_SIZE_BYTES) {
        toast.error("File too large. Max 50 MB allowed.");
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
        toast.error("Upload failed: " + (err.message ?? "please try again"));
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

  return (
    <div className="max-w-2xl mx-auto animate-fade-in p-6">
      <div className="mb-6">
        <h1 className="page-title">Upload</h1>
        <p className="page-subtitle">
          CSV, Excel, Tally XML — या ledger की photo (JPG/PNG)
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-5 gap-5">
        {/* Drop zone card */}
        <div className="md:col-span-3 card p-5">
          {(stage === "idle" || stage === "error") && (
            <>
              <div
                {...getRootProps()}
                className={cn(
                  "border-2 border-dashed rounded-xl p-10 text-center transition-all duration-200 cursor-pointer",
                  isDragActive
                    ? "border-orange-500 bg-orange-500/5"
                    : "border-border hover:border-orange-500/50 hover:bg-secondary/30",
                )}
              >
                <input {...getInputProps()} />
                <div className={cn(
                  "w-12 h-12 rounded-xl flex items-center justify-center mx-auto mb-3 transition-all",
                  isDragActive ? "bg-orange-500 text-white" : "bg-secondary",
                )}>
                  <Upload className={cn("w-6 h-6", isDragActive ? "text-white" : "text-muted-foreground")} />
                </div>

                {isDragActive ? (
                  <p className="text-orange-400 font-semibold text-sm">Release to upload</p>
                ) : (
                  <>
                    <p className="font-semibold text-foreground text-sm mb-1">
                      Drag and drop your file here
                    </p>
                    <p className="text-xs text-muted-foreground">or click to browse</p>
                  </>
                )}
              </div>

              <div className="flex items-center justify-center gap-5 mt-4">
                {[
                  { icon: FileText, label: "Tally XML", color: "text-orange-400" },
                  { icon: File,     label: "Excel",     color: "text-blue-400"   },
                  { icon: File,     label: "CSV",       color: "text-emerald-400"},
                  { icon: File,     label: "JPG/PNG",   color: "text-purple-400" },
                ].map((fmt) => (
                  <div key={fmt.label} className="flex items-center gap-1.5 text-xs text-muted-foreground">
                    <fmt.icon className={`w-3.5 h-3.5 ${fmt.color}`} />
                    {fmt.label}
                  </div>
                ))}
              </div>

              {error && (
                <div className="mt-4 bg-red-500/10 border border-red-500/20 rounded-xl px-4 py-3 flex items-start gap-2">
                  <AlertCircle className="w-4 h-4 text-red-400 mt-0.5 flex-shrink-0" />
                  <p className="text-xs text-red-400">{error}</p>
                </div>
              )}
            </>
          )}

          {(stage === "uploading" || stage === "processing" || stage === "done") && (
            <div className="text-center py-4">
              <div className="w-12 h-12 rounded-xl bg-orange-500/10 flex items-center justify-center mx-auto mb-3">
                <FileText className="w-6 h-6 text-orange-400" />
              </div>
              <p className="font-semibold text-foreground text-sm mb-0.5">{fileName}</p>
              <p className="text-xs text-muted-foreground">
                {stage === "uploading"  && "Uploading..."}
                {stage === "processing" && "AI is analysing your data..."}
                {stage === "done"       && "Analysis complete. Redirecting..."}
              </p>
              <Stepper stage={stage} />
              {stage === "processing" && (
                <p className="text-xs text-muted-foreground">This takes 10 to 30 seconds</p>
              )}
              {stage === "done" && (
                <div className="flex items-center justify-center gap-2 text-green-400 font-semibold text-xs mt-2">
                  <CheckCircle2 className="w-4 h-4" />
                  Analysis ready
                </div>
              )}
            </div>
          )}
        </div>

        {/* Instructions side card */}
        <div className="md:col-span-2 space-y-4">
          <div className="card p-4">
            <h3 className="font-semibold text-foreground text-sm mb-3">Export from Tally</h3>
            <ol className="space-y-2.5">
              {[
                "Open TallyPrime and go to Gateway of Tally",
                "Display > Reports > Statement of Accounts",
                "Export > select XML format",
                "Save and upload here",
              ].map((step, i) => (
                <li key={i} className="flex gap-2.5 text-xs text-muted-foreground">
                  <span className="font-bold text-orange-400 flex-shrink-0">{i + 1}.</span>
                  {step}
                </li>
              ))}
            </ol>
          </div>

          <div className="card p-4">
            <h3 className="font-semibold text-foreground text-sm mb-2">File limits</h3>
            <div className="space-y-1.5">
              {[
                ["Max size", "50 MB"],
                ["Formats", "XML, XLSX, XLS, CSV, JPG, PNG"],
                ["Processing time", "10 to 30 seconds"],
              ].map(([label, val]) => (
                <div key={label} className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">{label}</span>
                  <span className="font-semibold text-foreground">{val}</span>
                </div>
              ))}
            </div>
          </div>

          <Link
            href="/dashboard"
            className="flex items-center justify-between w-full text-xs text-muted-foreground hover:text-orange-400 transition-colors p-2"
          >
            Back to dashboard <ArrowRight className="w-3 h-3" />
          </Link>
        </div>
      </div>
    </div>
  );
}
