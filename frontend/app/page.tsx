"use client";
import RoundTripCard from "@/components/RoundTripCard";
import StatCard from "@/components/StatCard";
import {
  RoundTrip,
  Settings,
  TestNotifyResult,
  apiUrls,
  fetcher,
  sendTestNotification,
  triggerScan,
} from "@/lib/api";
import { useState } from "react";
import useSWR from "swr";

export default function Dashboard() {
  const { data: rts, mutate } = useSWR<RoundTrip[]>(apiUrls.roundTrips(20), fetcher);
  const { data: settings } = useSWR<Settings>(apiUrls.settings(), fetcher);
  const [scanning, setScanning] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<TestNotifyResult | null>(null);

  const onScan = async () => {
    setScanning(true);
    try {
      await triggerScan();
      await mutate();
    } finally {
      setScanning(false);
    }
  };

  const onTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      setTestResult(await sendTestNotification());
    } catch (e) {
      setTestResult({
        telegram_configured: false,
        discord_configured: false,
        telegram_sent: false,
        discord_sent: false,
        error: String(e),
      });
    } finally {
      setTesting(false);
    }
  };

  const cheapestTotal = rts && rts.length > 0
    ? Math.min(...rts.map((r) => r.total_price_twd))
    : null;

  return (
    <div className="space-y-8">
      <header className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold">Dashboard</h1>
          <p className="text-sm text-slate-400 mt-1">
            台灣 ↔ 日本 來回 · {settings?.airlines.join(" · ") || "..."}
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={onTest}
            disabled={testing}
            className="border border-ink-500 hover:bg-ink-700 disabled:opacity-50 text-slate-200 font-medium px-4 py-2 rounded-md text-sm"
          >
            {testing ? "送出中..." : "🧪 測試通知"}
          </button>
          <button
            onClick={onScan}
            disabled={scanning}
            className="bg-accent-500 hover:bg-accent-400 disabled:opacity-50 text-ink-900 font-medium px-4 py-2 rounded-md text-sm"
          >
            {scanning ? "掃描中..." : "🔍 立即掃描"}
          </button>
        </div>
      </header>

      {testResult && <TestResultBanner r={testResult} />}

      <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="最便宜來回"
          value={cheapestTotal ? `NT$ ${Math.round(cheapestTotal).toLocaleString()}` : "—"}
        />
        <StatCard label="組合數" value={rts?.length ?? 0} hint="符合 max_round_trip 的組合" />
        <StatCard label="航線" value={settings?.routes.length ?? 0} />
        <StatCard label="航空" value={settings?.airlines.length ?? 0} hint={settings?.airlines.join(" / ")} />
      </section>

      <section>
        <h2 className="text-lg font-semibold mb-3">🔥 Top 5 最便宜來回</h2>
        <div className="space-y-3">
          {(!rts || rts.length === 0) && (
            <div className="text-slate-500 text-sm bg-ink-800 border border-ink-600 rounded-lg p-5">
              尚未有資料 — 點上方「立即掃描」開始抓取（會掃台日雙向 + 配對 4-7 天停留）。
            </div>
          )}
          {rts?.slice(0, 5).map((r, idx) => (
            <RoundTripCard key={r.id} rt={r} rank={idx + 1} />
          ))}
        </div>
      </section>

      {rts && rts.length > 5 && (
        <section>
          <h2 className="text-lg font-semibold mb-3">其他組合（{rts.length - 5}）</h2>
          <div className="space-y-2">
            {rts.slice(5).map((r, idx) => (
              <RoundTripCard key={r.id} rt={r} rank={idx + 6} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

function TestResultBanner({ r }: { r: TestNotifyResult }) {
  if (r.error && !r.telegram_configured && !r.discord_configured) {
    return (
      <div className="bg-bad/15 border border-bad/40 text-slate-200 rounded-lg px-4 py-3 text-sm">
        ❌ 沒有設定任何通知通道 — 在 .env 填憑證後重啟後端再試。
      </div>
    );
  }
  const parts: string[] = [];
  if (r.telegram_configured) parts.push(r.telegram_sent ? "✅ Telegram 已送" : "❌ Telegram 失敗");
  if (r.discord_configured) parts.push(r.discord_sent ? "✅ Discord 已送" : "❌ Discord 失敗");
  const allOk =
    (r.telegram_configured ? r.telegram_sent : true) &&
    (r.discord_configured ? r.discord_sent : true);
  const tone = allOk ? "bg-good/15 border-good/40" : "bg-warn/15 border-warn/40";
  return (
    <div className={`${tone} border rounded-lg px-4 py-3 text-sm text-slate-200`}>
      測試訊息：{parts.join(" · ") || "（沒有設定任何通道）"}
    </div>
  );
}
