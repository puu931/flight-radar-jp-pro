"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  { href: "/", label: "📊 Dashboard" },
  { href: "/calendar", label: "📅 Calendar" },
  { href: "/trends", label: "📈 Trends" },
  { href: "/alerts", label: "🔔 Alerts" },
  { href: "/settings", label: "⚙️ Settings" },
];

export default function Sidebar() {
  const path = usePathname();
  return (
    <aside className="w-60 shrink-0 bg-ink-800 border-r border-ink-600 p-6">
      <div className="mb-8">
        <div className="text-lg font-bold leading-tight">✈️ Flight Radar</div>
        <div className="text-xs text-slate-400">JP Pro</div>
      </div>
      <nav className="flex flex-col gap-1">
        {NAV.map((item) => {
          const active = path === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`px-3 py-2 rounded-md text-sm transition-colors ${
                active
                  ? "bg-accent-500/20 text-accent-400"
                  : "text-slate-300 hover:bg-ink-700"
              }`}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>
      <div className="mt-10 text-xs text-slate-500 leading-relaxed">
        TPE / TSA / KHH<br />→ NRT · HND · KIX · FUK · OKA<br />
        BR · JX · CI
      </div>
    </aside>
  );
}
