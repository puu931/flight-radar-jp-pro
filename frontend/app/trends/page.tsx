"use client";
import PriceChart from "@/components/PriceChart";
import { TrendPoint, apiUrls, fetcher } from "@/lib/api";
import { useState } from "react";
import useSWR from "swr";

const ORIGINS = ["TPE", "TSA", "KHH"];
const DESTS = ["NRT", "HND", "KIX", "FUK", "OKA"];
const AIRLINES = ["", "BR", "JX", "CI"];

export default function TrendsPage() {
  const [origin, setOrigin] = useState("TPE");
  const [dest, setDest] = useState("NRT");
  const [airline, setAirline] = useState("");

  const { data: points } = useSWR<TrendPoint[]>(
    apiUrls.trends(origin, dest, airline || undefined),
    fetcher
  );

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold">📈 價格趨勢</h1>
        <p className="text-sm text-slate-400 mt-1">
          每次掃描記錄的最低價歷史
        </p>
      </header>

      <div className="flex gap-3 flex-wrap">
        <select
          value={origin}
          onChange={(e) => setOrigin(e.target.value)}
          className="bg-ink-700 border border-ink-600 rounded px-3 py-2 text-sm"
        >
          {ORIGINS.map((o) => <option key={o} value={o}>{o}</option>)}
        </select>
        <span className="self-center text-slate-500">→</span>
        <select
          value={dest}
          onChange={(e) => setDest(e.target.value)}
          className="bg-ink-700 border border-ink-600 rounded px-3 py-2 text-sm"
        >
          {DESTS.map((d) => <option key={d} value={d}>{d}</option>)}
        </select>
        <select
          value={airline}
          onChange={(e) => setAirline(e.target.value)}
          className="bg-ink-700 border border-ink-600 rounded px-3 py-2 text-sm"
        >
          {AIRLINES.map((a) => (
            <option key={a} value={a}>{a || "All airlines"}</option>
          ))}
        </select>
      </div>

      <PriceChart points={points || []} />
    </div>
  );
}
