export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        background: "#0a0e1a",
        surface: "#111827",
        border: "#1f2937",
        neon: "#00ff88",
        cyan: "#00d4ff",
        critical: "#ff3366",
        high: "#ff8c00",
        medium: "#ffd700",
        primary: "#e2e8f0",
        muted: "#64748b",
      },
      boxShadow: {
        glow: "0 0 28px rgba(0, 255, 136, 0.18)",
      },
    },
  },
  plugins: [],
};
