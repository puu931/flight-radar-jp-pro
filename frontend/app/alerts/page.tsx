"use client";
import { Alert, apiUrls, fetcher } from "@/lib/api";
import useSWR from "swr";

export default function AlertsPage() {
  const { data } = useSWR<Alert[]>(apiUrls.alerts(100), fetcher);

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold">🔔 通知紀錄</h1>
        <p className="text-sm text-slate-400 mt-1">
          已發送或已記錄的價格通知（最新 100 筆）
        </p>
      </header>

      <div className="bg-ink-800 border border-ink-600 rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-ink-700 text-slate-400 uppercase text-xs">
            <tr>
              <th className="text-left px-4 py-2">航線</th>
              <th className="text-left px-4 py-2">航空 / 航班</th>
              <th className="text-left px-4 py-2">出發</th>
              <th className="text-right px-4 py-2">價格</th>
              <th className="text-left px-4 py-2">通知時間</th>
              <th className="text-center px-4 py-2">送達</th>
            </tr>
          </thead>
          <tbody>
            {data?.length === 0 && (
              <tr>
                <td colSpan={6} className="text-center text-slate-500 py-6">
                  尚未有通知
                </td>
              </tr>
            )}
            {data?.map((a) => (
              <tr key={a.id} className="border-t border-ink-600">
                <td className="px-4 py-2 font-mono">{a.origin} → {a.destination}</td>
                <td className="px-4 py-2">{a.airline} {a.flight_number}</td>
                <td className="px-4 py-2 text-slate-400">
                  {new Date(a.departure_at).toLocaleString("zh-TW", {
                    month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit"
                  })}
                </td>
                <td className="px-4 py-2 text-right font-semibold">
                  NT$ {Math.round(a.price_twd).toLocaleString()}
                </td>
                <td className="px-4 py-2 text-slate-400">
                  {new Date(a.sent_at).toLocaleString("zh-TW")}
                </td>
                <td className="px-4 py-2 text-center">
                  {a.delivered ? "✅" : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
