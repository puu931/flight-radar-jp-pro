import "./globals.css";
import type { Metadata } from "next";
import Sidebar from "@/components/Sidebar";

export const metadata: Metadata = {
  title: "Flight Radar JP Pro",
  description: "Taiwan → Japan flight price intelligence",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-Hant">
      <body className="min-h-screen bg-ink-900 text-slate-100 font-sans">
        <div className="flex min-h-screen">
          <Sidebar />
          <main className="flex-1 p-8 overflow-x-hidden">{children}</main>
        </div>
      </body>
    </html>
  );
}
