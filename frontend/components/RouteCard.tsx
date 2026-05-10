import { Flight } from "@/lib/api";

const AIRLINE_NAME: Record<string, string> = {
  BR: "EVA Air",
  JX: "Starlux",
  CI: "China Airlines",
};

export default function RouteCard({ flight }: { flight: Flight }) {
  const dep = new Date(flight.departure_at);
  const arr = new Date(flight.arrival_at);
  const fmt = (d: Date) =>
    d.toLocaleString("zh-TW", {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  const dur = `${Math.floor(flight.duration_minutes / 60)}h${(flight.duration_minutes % 60)
    .toString()
    .padStart(2, "0")}m`;
  return (
    <div className="bg-ink-800 border border-ink-600 rounded-lg p-4 flex items-center gap-4">
      <div className="w-16 shrink-0">
        <div className="text-sm font-bold text-accent-400">{flight.airline}</div>
        <div className="text-xs text-slate-500">{AIRLINE_NAME[flight.airline] || flight.airline}</div>
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-sm">
          <span className="font-mono">{flight.origin}</span>
          <span className="mx-2 text-slate-500">→</span>
          <span className="font-mono">{flight.destination}</span>
          <span className="ml-3 text-slate-400">{flight.flight_number}</span>
        </div>
        <div className="text-xs text-slate-400 mt-1">
          {fmt(dep)} → {fmt(arr)} · {dur} · {flight.baggage_included ? "🧳 行李" : "⚠️ 無行李"} · {flight.fare_class}
        </div>
      </div>
      <div className="text-right">
        <div className="text-lg font-semibold">
          NT$ {Math.round(flight.price_twd).toLocaleString()}
        </div>
        {flight.deep_link && (
          <a
            href={flight.deep_link}
            target="_blank"
            rel="noreferrer"
            className="inline-block mt-1 text-xs text-accent-400 hover:underline"
          >
            訂票 →
          </a>
        )}
      </div>
    </div>
  );
}
