"use client";
import { Settings, apiUrls, fetcher } from "@/lib/api";
import useSWR from "swr";

export default function SettingsPage() {
  const { data } = useSWR<Settings>(apiUrls.settings(), fetcher);

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold">⚙️ Settings</h1>
        <p className="text-sm text-slate-400 mt-1">
          目前由 <code className="text-accent-400">config.yaml</code> 控制（v3 將開放 UI 編輯）
        </p>
      </header>

      {!data ? (
        <div className="text-slate-500">Loading…</div>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          <Card title="航空白名單">
            <div className="flex gap-2 flex-wrap">
              {data.airlines.map((a) => (
                <span key={a} className="bg-accent-500/20 text-accent-400 rounded px-2 py-1 text-sm">
                  {a}
                </span>
              ))}
            </div>
          </Card>

          <Card title="航線">
            <div className="space-y-2">
              {data.routes.map((r) => (
                <div key={`${r.origin}-${r.destination}`} className="flex justify-between text-sm">
                  <span className="font-mono">{r.origin} → {r.destination}</span>
                  <span className="text-slate-400">≤ NT$ {r.max_price.toLocaleString()}</span>
                </div>
              ))}
            </div>
          </Card>

          <Card title="篩選條件">
            <KV obj={data.filters} />
          </Card>

          <Card title="搜尋設定">
            <KV obj={data.search} />
          </Card>

          <Card title="通知">
            <KV obj={data.notification} />
          </Card>
        </div>
      )}
    </div>
  );
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-ink-800 border border-ink-600 rounded-lg p-5">
      <div className="text-sm font-semibold mb-3">{title}</div>
      {children}
    </div>
  );
}

function KV({ obj }: { obj: Record<string, unknown> }) {
  return (
    <div className="space-y-1 text-sm">
      {Object.entries(obj).map(([k, v]) => (
        <div key={k} className="flex justify-between">
          <span className="text-slate-400">{k}</span>
          <span className="font-mono">{String(Array.isArray(v) ? v.join(", ") : v)}</span>
        </div>
      ))}
    </div>
  );
}
