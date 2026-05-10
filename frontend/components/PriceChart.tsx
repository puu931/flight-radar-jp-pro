"use client";
import { TrendPoint } from "@/lib/api";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

export default function PriceChart({ points }: { points: TrendPoint[] }) {
  if (points.length === 0) {
    return <div className="text-slate-500 text-sm">沒有歷史資料 — 請先執行掃描</div>;
  }
  const data = points.map((p) => ({
    t: new Date(p.recorded_at).toLocaleDateString("zh-TW", {
      month: "2-digit",
      day: "2-digit",
    }),
    price: Math.round(p.min_price_twd),
  }));
  return (
    <div className="bg-ink-800 border border-ink-600 rounded-lg p-4 h-80">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
          <CartesianGrid stroke="#1f2430" strokeDasharray="3 3" />
          <XAxis dataKey="t" tick={{ fill: "#94a3b8", fontSize: 11 }} />
          <YAxis
            tick={{ fill: "#94a3b8", fontSize: 11 }}
            tickFormatter={(v) => `${v / 1000}k`}
          />
          <Tooltip
            contentStyle={{
              background: "#11141b",
              border: "1px solid #2a3140",
              borderRadius: 8,
              color: "#e6e8ee",
            }}
            formatter={(v: number) => [`NT$ ${v.toLocaleString()}`, "min price"]}
          />
          <Line type="monotone" dataKey="price" stroke="#5e9bff" strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
