"use client";
import { CalendarCell } from "@/lib/api";
import { addDays, format, startOfMonth, endOfMonth, getDay } from "date-fns";

function priceColor(price: number, min: number, max: number): string {
  if (max === min) return "bg-ok/30";
  const t = (price - min) / (max - min);
  if (t < 0.2) return "bg-good/70";
  if (t < 0.45) return "bg-ok/60";
  if (t < 0.7) return "bg-warn/60";
  return "bg-bad/60";
}

export default function CalendarHeatmap({ cells }: { cells: CalendarCell[] }) {
  if (cells.length === 0) {
    return <div className="text-slate-500 text-sm">沒有資料 — 請先執行掃描</div>;
  }

  const byDate: Record<string, CalendarCell> = Object.fromEntries(
    cells.map((c) => [c.date, c])
  );
  const prices = cells.map((c) => c.min_price_twd);
  const min = Math.min(...prices);
  const max = Math.max(...prices);

  const firstDate = new Date(cells[0].date);
  const lastDate = new Date(cells[cells.length - 1].date);

  // Group by month
  const months: Date[] = [];
  let cursor = startOfMonth(firstDate);
  while (cursor <= lastDate) {
    months.push(cursor);
    cursor = addDays(endOfMonth(cursor), 1);
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3 text-xs text-slate-400">
        <span>低價</span>
        <span className="w-4 h-4 rounded bg-good/70 inline-block" />
        <span className="w-4 h-4 rounded bg-ok/60 inline-block" />
        <span className="w-4 h-4 rounded bg-warn/60 inline-block" />
        <span className="w-4 h-4 rounded bg-bad/60 inline-block" />
        <span>高價</span>
        <span className="ml-4">區間 NT$ {Math.round(min).toLocaleString()} – {Math.round(max).toLocaleString()}</span>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {months.map((m) => (
          <MonthGrid key={m.toISOString()} month={m} byDate={byDate} min={min} max={max} />
        ))}
      </div>
    </div>
  );
}

function MonthGrid({
  month,
  byDate,
  min,
  max,
}: {
  month: Date;
  byDate: Record<string, CalendarCell>;
  min: number;
  max: number;
}) {
  const start = startOfMonth(month);
  const end = endOfMonth(month);
  const leadingBlanks = getDay(start); // 0 = Sun
  const days: (Date | null)[] = Array(leadingBlanks).fill(null);
  for (let d = new Date(start); d <= end; d = addDays(d, 1)) {
    days.push(new Date(d));
  }
  return (
    <div className="bg-ink-800 border border-ink-600 rounded-lg p-4">
      <div className="text-sm font-semibold mb-3">{format(month, "yyyy 年 MM 月")}</div>
      <div className="grid grid-cols-7 gap-1 text-[10px] text-slate-500 mb-1">
        {["日", "一", "二", "三", "四", "五", "六"].map((d) => (
          <div key={d} className="text-center">{d}</div>
        ))}
      </div>
      <div className="grid grid-cols-7 gap-1">
        {days.map((d, i) => {
          if (!d) return <div key={`b${i}`} />;
          const key = format(d, "yyyy-MM-dd");
          const cell = byDate[key];
          const color = cell ? priceColor(cell.min_price_twd, min, max) : "bg-ink-700";
          return (
            <div
              key={key}
              className={`aspect-square rounded ${color} text-[10px] flex flex-col items-center justify-center text-slate-100 px-1`}
              title={cell ? `${key}: NT$ ${Math.round(cell.min_price_twd).toLocaleString()}` : key}
            >
              <div className="font-mono leading-none">{format(d, "d")}</div>
              {cell && (
                <div className="leading-none mt-0.5 text-[9px] opacity-90">
                  {Math.round(cell.min_price_twd / 100) / 10}k
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
