import { RoundTrip } from "@/lib/api";

const AIRLINE: Record<string, string> = {
  BR: "EVA Air",
  JX: "Starlux",
  CI: "China Airlines",
};

function fmt(s: string) {
  const d = new Date(s);
  return d.toLocaleString("zh-TW", {
    month: "2-digit",
    day: "2-digit",
    weekday: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function RoundTripCard({ rt, rank }: { rt: RoundTrip; rank: number }) {
  return (
    <div className="bg-ink-800 border border-ink-600 rounded-lg p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="text-xs text-slate-400 mb-1">第 {rank} 便宜 · 停留 {rt.stay_days} 天</div>
          <div className="text-lg font-semibold">
            {rt.origin} ↔ {rt.destination}
          </div>
        </div>
        <div className="text-right">
          <div className="text-2xl font-bold text-accent-400">
            NT$ {Math.round(rt.total_price_twd).toLocaleString()}
          </div>
          <div className="text-xs text-slate-500">來回總價</div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-4">
        <Leg
          dir="🛫 去"
          airline={rt.out_airline}
          flight={rt.out_flight_number}
          dep={rt.out_departure_at}
          price={rt.out_price_twd}
          link={rt.out_deep_link}
        />
        <Leg
          dir="🛬 回"
          airline={rt.return_airline}
          flight={rt.return_flight_number}
          dep={rt.return_departure_at}
          price={rt.return_price_twd}
          link={rt.return_deep_link}
        />
      </div>
    </div>
  );
}

function Leg({
  dir,
  airline,
  flight,
  dep,
  price,
  link,
}: {
  dir: string;
  airline: string;
  flight: string;
  dep: string;
  price: number;
  link: string;
}) {
  const name = AIRLINE[airline] || airline;
  return (
    <div className="bg-ink-700 rounded-md p-3 text-sm">
      <div className="flex justify-between">
        <span className="font-medium">
          {dir}  <span className="text-accent-400">{airline}</span> {flight}
        </span>
        <span className="font-semibold">NT$ {Math.round(price).toLocaleString()}</span>
      </div>
      <div className="text-xs text-slate-400 mt-1">
        {fmt(dep)} · {name}
        {link && (
          <a
            href={link}
            target="_blank"
            rel="noreferrer"
            className="ml-2 text-accent-400 hover:underline"
          >
            訂票 →
          </a>
        )}
      </div>
    </div>
  );
}
