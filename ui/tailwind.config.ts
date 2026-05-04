import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        verdict: {
          pass: "#16a34a",
          weak: "#ca8a04",
          fail: "#dc2626",
        },
        compliance: {
          passed: "#16a34a",
          blocked: "#dc2626",
        },
      },
      fontFamily: {
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "Consolas", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
