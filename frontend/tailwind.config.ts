import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./pages/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./app/**/*.{ts,tsx}",
  ],
  theme: {
    container: { center: true, padding: "1.5rem", screens: { "2xl": "1400px" } },
    extend: {
      colors: {
        background:  "hsl(var(--background))",
        foreground:  "hsl(var(--foreground))",
        card: { DEFAULT: "hsl(var(--card))", foreground: "hsl(var(--card-foreground))" },
        popover: { DEFAULT: "hsl(var(--popover))", foreground: "hsl(var(--popover-foreground))" },
        primary: { DEFAULT: "hsl(var(--primary))", foreground: "hsl(var(--primary-foreground))" },
        secondary: { DEFAULT: "hsl(var(--secondary))", foreground: "hsl(var(--secondary-foreground))" },
        muted: { DEFAULT: "hsl(var(--muted))", foreground: "hsl(var(--muted-foreground))" },
        accent: { DEFAULT: "hsl(var(--accent))", foreground: "hsl(var(--accent-foreground))" },
        destructive: { DEFAULT: "hsl(var(--destructive))", foreground: "hsl(var(--destructive-foreground))" },
        border: "hsl(var(--border))",
        input:  "hsl(var(--input))",
        ring:   "hsl(var(--ring))",
      },
      fontFamily: {
        sans: ["var(--font-geist-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-geist-mono)", "monospace"],
      },
      fontSize: {
        "xs":   ["0.8125rem", { lineHeight: "1.25rem" }],
        "sm":   ["0.9375rem", { lineHeight: "1.5rem"  }],
        "base": ["1.0625rem", { lineHeight: "1.75rem" }],
        "lg":   ["1.1875rem", { lineHeight: "1.875rem"}],
        "xl":   ["1.3125rem", { lineHeight: "2rem"    }],
        "2xl":  ["1.5625rem", { lineHeight: "2.125rem"}],
        "3xl":  ["1.9375rem", { lineHeight: "2.375rem"}],
        "4xl":  ["2.4375rem", { lineHeight: "2.75rem" }],
        "5xl":  ["3.0625rem", { lineHeight: "1.1"     }],
        "6xl":  ["3.8125rem", { lineHeight: "1.1"     }],
      },
      borderRadius: {
        DEFAULT: "var(--radius)",
        lg:  "var(--radius)",
        xl:  "calc(var(--radius) + 2px)",
        "2xl": "calc(var(--radius) + 6px)",
        "3xl": "calc(var(--radius) + 12px)",
      },
      animation: {
        "fade-in":  "fadeIn 0.25s ease-out",
        "slide-up": "slideUp 0.3s ease-out",
        "shimmer":  "shimmer 2s infinite linear",
        "pulse-slow": "pulse 3s ease-in-out infinite",
      },
      keyframes: {
        fadeIn:  { from: { opacity: "0" }, to: { opacity: "1" } },
        slideUp: { from: { opacity: "0", transform: "translateY(10px)" }, to: { opacity: "1", transform: "translateY(0)" } },
        shimmer: {
          "0%":   { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition:  "200% 0" },
        },
      },
    },
  },
  plugins: [],
};

export default config;
