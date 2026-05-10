"use client";
import RouteCard from "@/components/RouteCard";
import StatCard from "@/components/StatCard";
import {
  Flight,
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
  const { data: flights, mutate } = useSWR<Flight[]>(apiUrls.cheapest(15), fetcher);
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
      const r = await sendTestNotification();
      setTestResult(r);
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

  const minPrice = flights && flights.length > 0
    ? Math.min(...flights.map((f) => f.price_twd))
    : null;

  return (
    <div className="space-y-8">
      <header className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold">Dashboard</h1>
          <p className="text-sm text-slate-400 mt-1">
            台灣 → 日本 · {settings?.airlines.join(" · ") || "..."}
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={onTest}
            disabled={testing}
            className="border border-ink-500 hover:bg-ink-700 disabled:opacity-50 text-slate-200 font-medium px-4 py-2 rounded-md text-sm"
            title="Send a sample alert to configured channels"
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
        <StatCard label="當前最低" value={minPrice ? `NT$ ${Math.round(minPrice).toLocaleString()}` : "—"} />
        <StatCard label="航班數" value={flights?.length ?? 0} hint="符合條件的便宜選項" />
        <StatCard label="航線" value={settings?.routes.length ?? 0} />
        <StatCard label="航空" value={settings?.airlines.length ?? 0} hint={settings?.airlines.join(" / ")} />
      </section>

      <section>
        <h2 className="text-lg font-semibold mb-3">🔥 最便宜的選項</h2>
        <div className="space-y-2">
          {flights?.length === 0 && (
            <div className="text-slate-500 text-sm">
              尚未有資料 — 點上方「立即掃描」開始抓取（mock 模式會生成範例資料）。
            </div>
          )}
          {flights?.map((f) => (
            <RouteCard key={f.id} flight={f} />
          ))}
        </div>
      </section>
    </div>
  );
}

function TestResultBanner({ r }: { r: TestNotifyResult }) {
  if (r.error && !r.telegram_configured && !r.discord_configured) {
    return (
      <div className="bg-bad/15 border border-bad/40 text-slate-200 rounded-lg px-4 py-3 text-sm">
        ❌ <b>沒有設定任何通知通道。</b><br />
        在 <code className="text-accent-400">.env</code> 填入 <code>BOT_TOKEN</code>+<code>CHAT_ID</code> 或 <code>DISCORD_WEBHOOK_URL</code>，重啟後端再試。
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
