/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: ["class"],
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Direction 4 ("Go all out") palette — pink field, navy ink, vivid orange.
        // Teal survives only as the supporting colour for cache / citation semantics.
        navy: {
          50: "#eef0f7",
          100: "#d7dcea",
          200: "#aab4d2",
          300: "#7c8ab5",
          400: "#4a5a8f",
          500: "#2c3a6e",
          600: "#232b4a",
          700: "#1e2a5c", // PRIMARY INK
          800: "#16224a",
          900: "#101a3a",
        },
        pink: {
          50: "#fdeef3",
          100: "#f9dbe6",
          200: "#f5c9d6", // HERO FIELD
          300: "#f3b8ca",
          400: "#efa9bf",
          500: "#e78ba9",
          600: "#d16a8c",
        },
        teal: {
          50: "#eef6f5",
          100: "#dcebe9",
          200: "#bcdcd9",
          300: "#7fb5b3",
          400: "#5fa8a6",
          500: "#2e7d7b", // SUPPORTING TEAL (cache / citations)
          600: "#256664",
          700: "#1d4f4e",
          800: "#173d3c",
          900: "#122e2d",
        },
        orange: {
          50: "#fff1e8",
          100: "#ffe0cc",
          200: "#ffc9a3",
          300: "#ffa76e",
          400: "#ff7a33",
          500: "#ff4d00", // VIVID ORANGE
          600: "#e04400",
          700: "#b23400",
          800: "#8f2a00",
          900: "#752200",
        },
        // Neutral surfaces (cream-first)
        surface: {
          50: "#ffffff",
          100: "#fff9f3", // CREAM BACKGROUND
          200: "#fdeef3",
          300: "#e8dfe4",
          400: "#c9b8c0",
          500: "#9aa0b8",
          600: "#6b7194",
          700: "#4a5170",
          800: "#232b4a",
          900: "#1e2a5c",
        },
      },
      fontFamily: {
        sans: ["var(--font-inter)", "Plus Jakarta Sans", "Inter", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "JetBrains Mono", "ui-monospace", "monospace"],
        display: ["Anton", "Arial Narrow", "sans-serif"],
        accent: ["Fraunces", "Georgia", "serif"],
      },
      boxShadow: {
        subtle: "0 1px 3px 0 rgba(30, 42, 92, 0.06)",
        card: "0 2px 12px -2px rgba(30, 42, 92, 0.07), 0 1px 3px 0 rgba(30, 42, 92, 0.04)",
        "card-hover": "0 8px 24px -4px rgba(30, 42, 92, 0.10), 0 2px 6px -1px rgba(30, 42, 92, 0.06)",
        orange: "0 4px 14px 0 rgba(255, 77, 0, 0.30)",
        teal: "0 4px 14px 0 rgba(46, 125, 123, 0.25)",
        pink: "5px 5px 0 #f5c9d6",
        "pink-sm": "3px 3px 0 #f5c9d6",
      },
      borderRadius: {
        xl: "12px",
        "2xl": "16px",
        "3xl": "20px",
      },
    },
  },
  plugins: [],
};
