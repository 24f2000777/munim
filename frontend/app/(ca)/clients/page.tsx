"use client";
import { useState } from "react";
import { useCAClients, useAddCAClient, useDeleteCAClient } from "@/lib/api/ca";
import { formatDate, relativeTime } from "@/lib/utils";
import {
  Users, Plus, X, Loader2, Phone,
  CheckCircle2, XCircle, ChevronLeft,
} from "lucide-react";
import Link from "next/link";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

function AddClientDialog({ onClose }: { onClose: () => void }) {
  const [name,  setName]  = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");

  const addMutation = useAddCAClient();

  const handleAdd = async () => {
    if (name.trim().length < 2) { toast.error("Name kam se kam 2 characters ka hona chahiye"); return; }
    try {
      await addMutation.mutateAsync({
        client_name:  name.trim(),
        client_phone: phone ? `+91${phone}` : undefined,
        client_email: email || undefined,
      });
      toast.success(`${name} add ho gaya! ✅`);
      onClose();
    } catch (e: any) {
      toast.error(e.message ?? "Failed to add client");
    }
  };

  return (
    <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-card border border-border rounded-2xl shadow-[0_32px_64px_rgba(0,0,0,0.15)] w-full max-w-sm animate-fade-in">
        <div className="flex items-center justify-between px-6 py-4 border-b border-border">
          <h2 className="font-bold text-forest">New Client Add Karo</h2>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-muted transition-colors">
            <X className="w-4 h-4 text-muted-foreground" />
          </button>
        </div>
        <div className="px-6 py-5 space-y-4">
          <div>
            <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1.5 block">
              Business Name *
            </label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Sharma Traders"
              className="w-full border border-border rounded-xl px-3 py-2.5 text-sm text-forest bg-card focus:outline-none focus:ring-2 focus:ring-saffron/30"
            />
          </div>
          <div>
            <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1.5 block flex items-center gap-1">
              <Phone className="w-3 h-3" /> Phone (WhatsApp)
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
          <div>
            <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1.5 block">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="client@example.com"
              className="w-full border border-border rounded-xl px-3 py-2.5 text-sm text-forest bg-card focus:outline-none focus:ring-2 focus:ring-saffron/30"
            />
          </div>
        </div>
        <div className="px-6 pb-5">
          <button
            onClick={handleAdd}
            disabled={addMutation.isPending || !name.trim()}
            className="w-full flex items-center justify-center gap-2 bg-forest hover:bg-forest-light disabled:opacity-50 text-cream font-semibold py-3 rounded-xl transition-all"
          >
            {addMutation.isPending ? (
              <><Loader2 className="w-4 h-4 animate-spin" /> Adding...</>
            ) : (
              <><Plus className="w-4 h-4" /> Client Add Karo</>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function ClientsPage() {
  const [showAdd, setShowAdd]   = useState(false);
  const [activeOnly, setActive] = useState(true);
  const { data, isLoading }     = useCAClients(activeOnly);
  const deleteMutation          = useDeleteCAClient();

  const handleDelete = async (id: string, name: string) => {
    if (!confirm(`"${name}" ko deactivate karna chahte ho?`)) return;
    try {
      await deleteMutation.mutateAsync(id);
      toast.success(`${name} deactivated`);
    } catch (e: any) {
      toast.error(e.message ?? "Failed");
    }
  };

  return (
    <div className="max-w-4xl mx-auto animate-fade-in">
      {showAdd && <AddClientDialog onClose={() => setShowAdd(false)} />}

      <Link href="/ca" className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-forest transition-colors mb-5">
        <ChevronLeft className="w-4 h-4" /> CA Dashboard
      </Link>

      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-forest">Clients</h1>
          <p className="text-sm text-muted-foreground mt-0.5">{data?.total ?? 0} clients</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => setActive((v) => !v)}
            className={cn(
              "text-xs font-semibold px-3 py-1.5 rounded-xl border transition-colors",
              activeOnly ? "bg-forest/10 border-forest/20 text-forest" : "bg-muted border-border text-muted-foreground",
            )}
          >
            {activeOnly ? "Active only" : "All clients"}
          </button>
          <button
            onClick={() => setShowAdd(true)}
            className="inline-flex items-center gap-2 bg-saffron hover:bg-saffron-dark text-white font-semibold text-sm px-4 py-2 rounded-xl shadow-warm transition-all"
          >
            <Plus className="w-4 h-4" /> Add Client
          </button>
        </div>
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {Array(4).fill(0).map((_, i) => <div key={i} className="skeleton h-16 rounded-2xl" />)}
        </div>
      ) : !data?.items?.length ? (
        <div className="text-center py-20 bg-card border border-border rounded-2xl">
          <Users className="w-12 h-12 text-muted-foreground/40 mx-auto mb-3" />
          <p className="font-semibold text-forest">Koi clients nahi hai</p>
          <p className="text-sm text-muted-foreground mt-1 mb-5">Apna pehla client add karo</p>
          <button
            onClick={() => setShowAdd(true)}
            className="inline-flex items-center gap-2 bg-saffron/10 hover:bg-saffron/20 text-saffron font-semibold text-sm px-4 py-2 rounded-xl transition-colors"
          >
            <Plus className="w-4 h-4" /> Add Client
          </button>
        </div>
      ) : (
        <div className="bg-card border border-border rounded-2xl shadow-metric overflow-hidden">
          {data.items.map((client, i) => (
            <div
              key={client.client_id}
              className={cn(
                "flex items-center gap-4 px-5 py-4 hover:bg-muted/40 transition-colors",
                i > 0 ? "border-t border-border/60" : "",
              )}
            >
              {/* Avatar */}
              <div className="w-10 h-10 rounded-xl bg-forest/10 flex items-center justify-center text-forest font-bold text-sm flex-shrink-0">
                {client.client_name.slice(0, 1).toUpperCase()}
              </div>

              {/* Info */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap mb-0.5">
                  <p className="font-semibold text-forest text-sm">{client.client_name}</p>
                  {!client.active && (
                    <span className="text-[10px] bg-red-50 text-red-600 border border-red-200 px-1.5 py-0.5 rounded-full font-semibold">Inactive</span>
                  )}
                  {client.whatsapp_opted_in && (
                    <span className="text-[10px] bg-green-50 text-green-700 border border-green-200 px-1.5 py-0.5 rounded-full font-semibold">WA ✓</span>
                  )}
                </div>
                <p className="text-xs text-muted-foreground">
                  {client.client_phone ?? client.client_email ?? "No contact"} ·{" "}
                  {client.upload_count} upload{client.upload_count !== 1 ? "s" : ""} ·{" "}
                  {client.last_upload_at ? relativeTime(client.last_upload_at) : "Never uploaded"}
                </p>
              </div>

              {/* Actions */}
              <div className="flex items-center gap-2 flex-shrink-0">
                {client.active && (
                  <button
                    onClick={() => handleDelete(client.client_id, client.client_name)}
                    className="p-2 rounded-lg hover:bg-red-50 text-muted-foreground hover:text-red-600 transition-colors"
                    title="Deactivate"
                  >
                    <X className="w-4 h-4" />
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
