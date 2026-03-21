"use client";
import { useCADashboard } from "@/lib/api/ca";
import { MetricCard } from "@/components/dashboard/MetricCard";
import { AlertTriangle, Users, Upload, BarChart3, ArrowRight } from "lucide-react";
import { relativeTime } from "@/lib/utils";
import Link from "next/link";

export default function CAPortalPage() {
  const { data, isLoading } = useCADashboard();

  return (
    <div className="p-6 animate-fade-in">

      {/* Header */}
      <div className="mb-8">
        <div className="inline-flex items-center gap-2 bg-amber-500/10 border border-amber-500/20 text-amber-500 text-xs font-semibold px-3 py-1.5 rounded-full mb-3">
          <BarChart3 className="w-3.5 h-3.5" />
          CA Firm Portal
        </div>
        <h1 className="text-2xl font-bold text-foreground">Portfolio Dashboard</h1>
        <p className="text-sm text-muted-foreground mt-0.5">Overview of all your clients</p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <MetricCard
          label="Total Clients"
          value={isLoading ? "—" : String(data?.total_clients ?? 0)}
          icon={<Users className="w-4 h-4 text-emerald-500" />}
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
          icon={<Upload className="w-4 h-4 text-amber-500" />}
          accent="golden"
          loading={isLoading}
        />
        <MetricCard
          label="At Risk"
          value={isLoading ? "—" : String(data?.at_risk_clients ?? 0)}
          icon={<AlertTriangle className="w-4 h-4 text-red-400" />}
          accent={data?.at_risk_clients ? "red" : "forest" as any}
          loading={isLoading}
        />
      </div>

      {/* Clients needing attention */}
      {data?.high_alert_clients?.length ? (
        <div className="card p-5 mb-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-red-400" />
              <h2 className="font-semibold text-foreground">Clients Needing Attention</h2>
            </div>
            <Link
              href="/clients"
              className="text-xs text-orange-400 font-semibold hover:text-orange-300 flex items-center gap-1"
            >
              All clients <ArrowRight className="w-3 h-3" />
            </Link>
          </div>
          <div className="space-y-2">
            {data.high_alert_clients.map((client) => (
              <div
                key={client.client_id}
                className="flex items-center gap-3 p-3 rounded-xl bg-red-500/5 border border-red-500/15 hover:bg-red-500/10 transition-colors"
              >
                <div className="w-8 h-8 rounded-full bg-red-500/15 flex items-center justify-center text-red-400 text-xs font-bold flex-shrink-0">
                  {client.client_name.slice(0, 1).toUpperCase()}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-foreground truncate">{client.client_name}</p>
                  <p className="text-xs text-muted-foreground">
                    {client.last_upload ? relativeTime(client.last_upload) : "No uploads yet"}
                  </p>
                </div>
                <span className="badge badge-high flex-shrink-0 text-xs">
                  {client.high_alerts} HIGH
                </span>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {/* Quick actions */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Link
          href="/clients"
          className="flex items-center gap-4 p-5 rounded-2xl bg-emerald-600 hover:bg-emerald-500 text-white font-semibold transition-all hover:-translate-y-0.5 shadow-lg"
        >
          <div className="w-10 h-10 rounded-xl bg-white/20 flex items-center justify-center flex-shrink-0">
            <Users className="w-5 h-5" />
          </div>
          <div className="flex-1">
            <p className="text-sm font-bold">Manage Clients</p>
            <p className="text-xs text-white/70 mt-0.5">View and manage client accounts</p>
          </div>
          <ArrowRight className="w-4 h-4 opacity-60 flex-shrink-0" />
        </Link>

        <Link
          href="/upload"
          className="flex items-center gap-4 p-5 rounded-2xl bg-orange-500 hover:bg-orange-400 text-white font-semibold transition-all hover:-translate-y-0.5 shadow-lg"
        >
          <div className="w-10 h-10 rounded-xl bg-white/20 flex items-center justify-center flex-shrink-0">
            <Upload className="w-5 h-5" />
          </div>
          <div className="flex-1">
            <p className="text-sm font-bold">Upload for Client</p>
            <p className="text-xs text-white/70 mt-0.5">Upload and analyse a client's file</p>
          </div>
          <ArrowRight className="w-4 h-4 opacity-60 flex-shrink-0" />
        </Link>
      </div>
    </div>
  );
}
