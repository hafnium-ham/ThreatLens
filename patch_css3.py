with open("frontend/src/styles.css", "a") as f:
    f.write("""
/* ─── Agent Active Effects ─────────────────────────────────── */
.app-shell.agent-active {
  box-shadow: inset 0 0 120px rgba(0, 255, 136, 0.15);
  border: 1px solid rgba(0, 255, 136, 0.3);
  animation: agent-shell-pulse 2s ease-in-out infinite alternate;
}

@keyframes agent-shell-pulse {
  from { box-shadow: inset 0 0 60px rgba(0, 255, 136, 0.05); }
  to { box-shadow: inset 0 0 120px rgba(0, 255, 136, 0.2); }
}

/* ─── Button Enhancements ──────────────────────────────────── */
.tab-btn {
  position: relative;
  overflow: hidden;
}

.tab-btn::after {
  content: '';
  position: absolute;
  bottom: 0; left: 0; right: 0;
  height: 2px;
  background: var(--neon);
  transform: scaleX(0);
  transition: transform 0.2s ease;
}

.tab-btn:hover::after {
  transform: scaleX(1);
}

.tab-btn.active {
  background: linear-gradient(0deg, rgba(0, 255, 136, 0.1) 0%, transparent 100%);
  color: var(--neon);
  box-shadow: inset 0 -2px 10px rgba(0, 255, 136, 0.1);
}

.filter-group button:hover {
  background: rgba(0, 212, 255, 0.05);
  border-color: var(--cyan);
  color: var(--cyan);
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(0, 212, 255, 0.1);
}

.filter-group button.active-filter {
  background: linear-gradient(135deg, rgba(0, 255, 136, 0.15), rgba(0, 255, 136, 0.05));
  border-color: var(--neon);
  color: var(--neon);
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0, 255, 136, 0.2);
}

.agent-trigger-btn.running {
  background: rgba(0, 255, 136, 0.15) !important;
  color: var(--neon) !important;
  border-color: var(--neon) !important;
  box-shadow: 0 0 30px rgba(0, 255, 136, 0.5), inset 0 0 20px rgba(0, 255, 136, 0.2) !important;
  animation: agent-btn-pulse 1.5s infinite alternate;
}

@keyframes agent-btn-pulse {
  from { box-shadow: 0 0 15px rgba(0, 255, 136, 0.3), inset 0 0 10px rgba(0, 255, 136, 0.1); }
  to { box-shadow: 0 0 40px rgba(0, 255, 136, 0.6), inset 0 0 20px rgba(0, 255, 136, 0.3); text-shadow: 0 0 8px rgba(0, 255, 136, 0.8); }
}
""")
