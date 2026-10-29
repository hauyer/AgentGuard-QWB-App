const statusTones = {
  emerald: ["#12352f", "#244c40", "#72dbb5"], green: ["#12352f", "#244c40", "#72dbb5"],
  amber: ["#342a1c", "#55432c", "#f0c16b"], yellow: ["#342a1c", "#55432c", "#f0c16b"],
  red: ["#351e2b", "#5c3242", "#f49aab"], orange: ["#35271e", "#5b412e", "#ecb181"],
  rose: ["#351e2b", "#5c3242", "#f49aab"],
  blue: ["#172d46", "#2d4d6d", "#91c4f9"], sky: ["#162e42", "#284b64", "#89cef1"],
  violet: ["#28213c", "#4c3d68", "#c2aff3"], purple: ["#28213c", "#4c3d68", "#c2aff3"],
  cyan: ["#123039", "#26515a", "#83d7df"], indigo: ["#22273f", "#3d496c", "#b6c2f3"],
};
const backgrounds = Object.fromEntries(Object.entries(statusTones).map(([name, [base]]) => [name, {50:base,100:base}]));
const borders = Object.fromEntries(Object.entries(statusTones).map(([name, [,border]]) => [name, {100:border,200:border,300:border}]));
const foregrounds = Object.fromEntries(Object.entries(statusTones).map(([name, [,,ink]]) => [name, {600:ink,700:ink,800:ink,900:ink}]));
/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      backgroundColor: { white:"#101d2e", slate:{50:"#142238",100:"#1b2b41",200:"#263a51",300:"#40516a"}, ...backgrounds },
      borderColor: { slate:{100:"#23354b",200:"#2d4158",300:"#455a72"}, ...borders },
      ringColor: { slate:{200:"#2d4158",300:"#455a72"} },
      textColor: { slate:{300:"#aabed2",400:"#93aac1",500:"#99aec4",600:"#b3c5d8",700:"#c9d7e8",800:"#dfeaf7",900:"#eef5ff",950:"#f5f9ff"}, ...foregrounds },
      colors: {
        brand: {
          50: "rgb(var(--color-brand-50-rgb) / <alpha-value>)",
          100: "rgb(var(--color-brand-100-rgb) / <alpha-value>)",
          500: "rgb(var(--color-brand-500-rgb) / <alpha-value>)",
          600: "rgb(var(--color-brand-600-rgb) / <alpha-value>)",
          700: "rgb(var(--color-brand-700-rgb) / <alpha-value>)",
          900: "rgb(var(--color-brand-900-rgb) / <alpha-value>)",
          950: "rgb(var(--color-brand-950-rgb) / <alpha-value>)",
        },
        surface: {
          DEFAULT: "rgb(var(--color-surface-rgb) / <alpha-value>)",
          muted: "rgb(var(--color-surface-muted-rgb) / <alpha-value>)",
          border: "rgb(var(--color-surface-border-rgb) / <alpha-value>)",
        },
        semantic: {
          ok: "rgb(var(--color-ok-rgb) / <alpha-value>)",
          warn: "rgb(var(--color-warn-rgb) / <alpha-value>)",
          danger: "rgb(var(--color-danger-rgb) / <alpha-value>)",
          info: "rgb(var(--color-info-rgb) / <alpha-value>)",
          neutral: "rgb(var(--color-neutral-rgb) / <alpha-value>)",
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
