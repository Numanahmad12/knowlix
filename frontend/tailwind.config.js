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
        // Official Knowlix Brand Palette
        teal: {
          50: "#f3f8f8",
          100: "#e5f0f0",
          200: "#d0e4e3",
          300: "#a8c9c8", // OFFICIAL PRIMARY TEAL
          400: "#86b3b2",
          500: "#5a9695",
          600: "#447877",
          700: "#375f5f",
          800: "#2e4d4d",
          900: "#274141",
        },
        orange: {
          50: "#fef5f0",
          100: "#fde9dc",
          200: "#fbd1b8",
          300: "#f8b189",
          400: "#f68652",
          500: "#f45b0b", // OFFICIAL VIBRANT ORANGE
          600: "#dc4805",
          700: "#b73507",
          800: "#912c0d",
          900: "#75260e",
        },
        // Neutral Slate-Teal Surfaces (Light-first)
        surface: {
          50: "#ffffff",
          100: "#f8fafa",
          200: "#f1f5f5",
          300: "#e4ebeb",
          400: "#cbd6d6",
          500: "#94a3a3",
          600: "#647474",
          700: "#334141",
          800: "#1e2929",
          900: "#0f1717",
        },
      },
      fontFamily: {
        sans: ["var(--font-inter)", "Plus Jakarta Sans", "Inter", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "JetBrains Mono", "ui-monospace", "monospace"],
      },
      boxShadow: {
        subtle: "0 1px 3px 0 rgba(15, 23, 23, 0.05)",
        card: "0 2px 12px -2px rgba(15, 23, 23, 0.06), 0 1px 3px 0 rgba(15, 23, 23, 0.04)",
        "card-hover": "0 8px 24px -4px rgba(15, 23, 23, 0.1), 0 2px 6px -1px rgba(15, 23, 23, 0.06)",
        orange: "0 4px 14px 0 rgba(244, 91, 11, 0.28)",
        teal: "0 4px 14px 0 rgba(168, 201, 200, 0.35)",
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
