"use client";
import CalendarHeatmap from "@/components/CalendarHeatmap";
import { CalendarCell, Settings, apiUrls, fetcher } from "@/lib/api";
import { useState } from "react";
import useSWR from "swr";

const ORIGINS = ["TPE", "TSA", "KHH"];
const DESTS = ["NRT", "HND", "KIX", "FUK", "OKA"];

export default function CalendarPage() {
  const { data: settings } = useSWR<Settings>(apiUrls.settings(), fetcher);
  const [origin, setOrigin] = useState("TPE");
  const [dest, setDest] = useState("NRT");

  const { data: cells } = useSWR<CalendarCell[]>(
    apiUrls.calendar(origin, dest, 90),
    fetcher
  );

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold">📅 低價日曆</h1>
        <p className="text-sm text-slate-400 mt-1">
          顏色越深越貴 — 該日出發的<b>來回最便宜總價</b>（停留 4-7 天）
        </p>
      </header>

      <div className="flex gap-3 flex-wrap">
        <select
          value={origin}
          onChange={(e) => setOrigin(e.target.value)}
          className="bg-ink-700 border border-ink-600 rounded px-3 py-2 text-sm"
        >
          {ORIGINS.map((o) => (
            <option key={o} value={o}>{o}</option>
          ))}
        </select>
        <span className="self-center text-slate-500">→</span>
        <select
          value={dest}
          onChange={(e) => setDest(e.target.value)}
          className="bg-ink-700 border border-ink-600 rounded px-3 py-2 text-sm"
        >
          {DESTS.map((d) => (
            <option key={d} value={d}>{d}</option>
          ))}
        </select>
      </div>

      <CalendarHeatmap cells={cells || []} />
    </div>
  );
}
