import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./pages/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./app/**/*.{ts,tsx}",
  ],
  theme: {
    container: {
      center: true,
      padding: "1rem",
      screens: { "2xl": "1400px" },
    },
    extend: {
      colors: {
        saffron: {
          DEFAULT: "#E8651A",
          light: "#F08040",
          dark: "#C04E0D",
        },
        forest: {
          DEFAULT: "#1B4332",
          light: "#2D6A4F",
          dark: "#0D2B1F",
        },
        golden: {
          DEFAULT: "#F9A826",
          light: "#FBBB50",
          dark: "#D4870A",
        },
        cream: {
          DEFAULT: "#FAFAF7",
          dark: "#F0F0E8",
        },
        background:  "hsl(var(--background))",
        foreground:  "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        border: "hsl(var(--border))",
        input:  "hsl(var(--input))",
        ring:   "hsl(var(--ring))",
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
      },
      fontFamily: {
        sans:  ["var(--font-inter)", "Noto Sans Devanagari", "sans-serif"],
        hindi: ["var(--font-noto-devanagari)", "sans-serif"],
        mono:  ["var(--font-geist-mono)", "monospace"],
      },
      borderRadius: {
        lg:   "var(--radius)",
        md:   "calc(var(--radius) - 2px)",
        sm:   "calc(var(--radius) - 4px)",
        xl:   "1rem",
        "2xl":"1.25rem",
        "3xl":"1.5rem",
      },
      boxShadow: {
        warm:   "0 4px 24px 0 rgba(232, 101, 26, 0.12)",
        card:   "0 2px 16px 0 rgba(27, 67, 50, 0.07)",
        metric: "0 1px 4px 0 rgba(27, 67, 50, 0.10), 0 4px 16px 0 rgba(27, 67, 50, 0.06)",
        glow:   "0 0 40px rgba(232, 101, 26, 0.15)",
      },
      keyframes: {
        "accordion-down": {
          from: { height: "0" },
          to:   { height: "var(--radix-accordion-content-height)" },
        },
        "accordion-up": {
          from: { height: "var(--radix-accordion-content-height)" },
          to:   { height: "0" },
        },
        "fade-in": {
          from: { opacity: "0", transform: "translateY(10px)" },
          to:   { opacity: "1", transform: "translateY(0)" },
        },
        "fade-in-fast": {
          from: { opacity: "0" },
          to:   { opacity: "1" },
        },
        "slide-up": {
          from: { opacity: "0", transform: "translateY(20px)" },
          to:   { opacity: "1", transform: "translateY(0)" },
        },
        shimmer: {
          "0%":   { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        "count-up": {
          from: { opacity: "0", transform: "translateY(4px)" },
          to:   { opacity: "1", transform: "translateY(0)" },
        },
        float: {
          "0%, 100%": { transform: "translateY(0)" },
          "50%":      { transform: "translateY(-8px)" },
        },
        "pulse-ring": {
          "0%":   { transform: "scale(1)", opacity: "0.8" },
          "100%": { transform: "scale(1.4)", opacity: "0" },
        },
      },
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up":   "accordion-up 0.2s ease-out",
        "fade-in":        "fade-in 0.4s ease-out",
        "fade-in-fast":   "fade-in-fast 0.2s ease-out",
        "slide-up":       "slide-up 0.5s ease-out",
        shimmer:          "shimmer 2s linear infinite",
        "count-up":       "count-up 0.3s ease-out",
        float:            "float 3s ease-in-out infinite",
        "pulse-ring":     "pulse-ring 1.5s ease-out infinite",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};

export default config;
