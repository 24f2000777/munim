"use client";
import { useCADashboard } from "@/lib/api/ca";
import { MetricCard } from "@/components/dashboard/MetricCard";
import { AlertTriangle, Users, Upload, BarChart3, ArrowRight } from "lucide-react";
import { formatDate, relativeTime } from "@/lib/utils";
import Link from "next/link";

export default function CAPortalPage() {
  const { data, isLoading } = useCADashboard();

  return (
    <div className="animate-fade-in">
      <div className="mb-8">
        <div className="inline-flex items-center gap-2 bg-golden/10 border border-golden/20 text-golden-dark text-xs font-semibold px-3 py-1.5 rounded-full mb-3">
          <BarChart3 className="w-3.5 h-3.5" />
          CA Firm Portal
        </div>
        <h1 className="text-2xl font-bold text-forest">Portfolio Dashboard</h1>
        <p className="text-sm text-muted-foreground mt-0.5">Apne sabhi clients ka overview</p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <MetricCard
          label="Total Clients"
          value={isLoading ? "—" : String(data?.total_clients ?? 0)}
          icon={<Users className="w-4 h-4 text-forest" />}
          accent="forest"
          loading={isLoading}
        />
        <MetricCard
          label="Active"
          value={isLoading ? "—" : String(data?.active_clients ?? 0)}
          accent="saffron"
          loading={isLoading}
        />
        <MetricCard
          label="Total Uploads"
          value={isLoading ? "—" : String(data?.total_uploads ?? 0)}
          icon={<Upload className="w-4 h-4 text-golden-dark" />}
          accent="golden"
          loading={isLoading}
        />
        <MetricCard
          label="At Risk"
          value={isLoading ? "—" : String(data?.at_risk_clients ?? 0)}
          icon={<AlertTriangle className="w-4 h-4 text-red-500" />}
          accent={data?.at_risk_clients ? "red" : "forest"}
          loading={isLoading}
        />
      </div>

      {/* High alert clients */}
      {data?.high_alert_clients?.length ? (
        <div className="bg-card border border-border rounded-2xl shadow-metric p-5 mb-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-red-500" />
              <h2 className="font-semibold text-forest">Clients Needing Attention</h2>
            </div>
            <Link href="/clients" className="text-xs text-saffron font-semibold hover:text-saffron-dark flex items-center gap-1">
              All clients <ArrowRight className="w-3 h-3" />
            </Link>
          </div>
          <div className="space-y-2">
            {data.high_alert_clients.map((client) => (
              <div key={client.client_id} className="flex items-center gap-3 p-3 rounded-xl hover:bg-muted/60 transition-colors bg-red-50/50 border border-red-100">
                <div className="w-8 h-8 rounded-full bg-red-100 flex items-center justify-center text-red-600 text-xs font-bold flex-shrink-0">
                  {client.client_name.slice(0, 1)}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-forest truncate">{client.client_name}</p>
                  <p className="text-xs text-muted-foreground">
                    {client.last_upload ? relativeTime(client.last_upload) : "No uploads"}
                  </p>
                </div>
                <span className="badge-high flex-shrink-0">
                  {client.high_alerts} HIGH
                </span>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {/* Quick actions */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Link href="/clients" className="bg-forest hover:bg-forest-light text-cream font-semibold py-4 px-5 rounded-2xl flex items-center gap-3 transition-all hover:-translate-y-0.5 shadow-card">
          <Users className="w-5 h-5" />
          <div>
            <p className="text-sm font-bold">Manage Clients</p>
            <p className="text-xs text-cream/70">Client list aur details</p>
          </div>
          <ArrowRight className="w-4 h-4 ml-auto opacity-60" />
        </Link>
        <Link href="/upload" className="bg-saffron hover:bg-saffron-dark text-white font-semibold py-4 px-5 rounded-2xl flex items-center gap-3 transition-all hover:-translate-y-0.5 shadow-warm">
          <Upload className="w-5 h-5" />
          <div>
            <p className="text-sm font-bold">Upload for Client</p>
            <p className="text-xs text-white/70">File upload karo</p>
          </div>
          <ArrowRight className="w-4 h-4 ml-auto opacity-60" />
        </Link>
      </div>
    </div>
  );
}
