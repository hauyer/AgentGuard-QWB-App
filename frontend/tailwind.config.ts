/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Modern security-platform palette: deep blue, white, grey.
        brand: {
          50: "#f0f5ff",
          100: "#e0ebff",
          500: "#2563eb",
          600: "#1d4ed8",
          700: "#1e40af",
          900: "#0f2a63",
          950: "#0a1a3f",
        },
        surface: {
          DEFAULT: "#ffffff",
          muted: "#f5f7fa",
          border: "#d7dde6",
        },
        semantic: {
          ok: "#16a34a",
          warn: "#d97706",
          danger: "#dc2626",
          info: "#2563eb",
          neutral: "#6b7280",
        },
      },
      fontFamily: {
        sans: [
          "Inter",
          "PingFang SC",
          "Microsoft YaHei",
          "Noto Sans SC",
          "system-ui",
          "sans-serif",
        ],
        mono: ["JetBrains Mono", "SFMono-Regular", "Consolas", "monospace"],
      },
    },
  },
  plugins: [],
};
