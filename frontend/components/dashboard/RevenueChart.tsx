"use client";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer,
} from "recharts";
import { formatINR } from "@/lib/utils";

interface DataPoint {
  date:    string;
  revenue: number;
}

interface RevenueChartProps {
  data: DataPoint[];
}

function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-card border border-border rounded-xl px-4 py-3 shadow-metric">
      <p className="text-xs font-semibold text-muted-foreground mb-1">{label}</p>
      <p className="text-base font-bold text-foreground">
        {formatINR(payload[0].value)}
      </p>
    </div>
  );
}

export function RevenueChart({ data }: RevenueChartProps) {
  if (!data.length) {
    return (
      <div className="h-48 flex items-center justify-center text-sm text-muted-foreground bg-muted/30 rounded-xl">
        No data yet — upload your first file
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={200}>
      <AreaChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
        <defs>
          <linearGradient id="revenueGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%"   stopColor="#E8651A" stopOpacity={0.2} />
            <stop offset="100%" stopColor="#E8651A" stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <CartesianGrid vertical={false} strokeDasharray="3 3" stroke="hsl(48, 15%, 88%)" />
        <XAxis
          dataKey="date"
          tick={{ fontSize: 11 }}
          tickLine={false}
          axisLine={false}
        />
        <YAxis
          tickFormatter={(v) => formatINR(v, true)}
          tick={{ fontSize: 11 }}
          tickLine={false}
          axisLine={false}
          width={60}
        />
        <Tooltip content={<CustomTooltip />} />
        <Area
          type="monotone"
          dataKey="revenue"
          stroke="#E8651A"
          strokeWidth={2.5}
          fill="url(#revenueGrad)"
          dot={false}
          activeDot={{ r: 5, strokeWidth: 0, fill: "#E8651A" }}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
