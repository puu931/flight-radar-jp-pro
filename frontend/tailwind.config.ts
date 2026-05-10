import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: {
          900: "#0b0d12",
          800: "#11141b",
          700: "#181c25",
          600: "#1f2430",
          500: "#2a3140",
        },
        accent: {
          500: "#5e9bff",
          400: "#7eb1ff",
        },
        good: "#22c55e",
        ok: "#84cc16",
        warn: "#eab308",
        bad: "#ef4444",
      },
      fontFamily: {
        sans: ["ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "Roboto"],
      },
    },
  },
  plugins: [],
};

export default config;
