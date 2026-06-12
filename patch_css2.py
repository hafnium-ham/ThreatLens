with open("frontend/src/styles.css", "a") as f:
    f.write("""
/* ─── Analytics Bar ────────────────────────────────────────── */
.analytics-bar {
  display: flex;
  flex-wrap: wrap;
  gap: .65rem;
}

.analytics-bar > .stat,
.analytics-bar > .mini-chart {
  flex: 1 1 120px;
  min-width: 100px;
}

.analytics-bar > .benchmark-panel {
  flex: 1 1 100%;
}

.stat {
  border: 1px solid var(--border);
  border-radius: .45rem;
  background: #080d18;
  padding: .75rem;
}

.stat span {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  font-size: .68rem;
  text-transform: uppercase;
  letter-spacing: .08em;
  color: var(--muted);
}

.stat strong {
  display: block;
  margin-top: .35rem;
  font-size: 1.3rem;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.threat-velocity .velocity-compare {
  font-size: 0.65rem;
  color: var(--muted);
  margin-top: 0.15rem;
}

.mini-chart {
  border: 1px solid var(--border);
  border-radius: .45rem;
  background: #080d18;
  padding: .35rem;
}

/* ─── Benchmark Panel ──────────────────────────────────────── */
.benchmark-panel {
  border: 1px solid var(--border);
  border-radius: 0.45rem;
  background: #050a12;
  padding: 0.75rem;
}

.benchmark-title {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  color: var(--neon);
  font-size: 0.72rem;
  font-weight: 900;
  letter-spacing: 0.1em;
  margin-bottom: 0.6rem;
  text-transform: uppercase;
}

.benchmark-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.5rem;
}

.benchmark-card {
  border: 1px solid var(--border);
  border-radius: 0.35rem;
  background: #080d18;
  padding: 0.6rem;
}

.benchmark-query {
  color: var(--muted);
  font-size: 0.65rem;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  margin-bottom: 0.4rem;
}

.benchmark-time {
  color: var(--neon);
  font-size: 0.75rem;
  font-weight: 700;
}

.benchmark-time strong {
  font-size: 1.2rem;
  color: var(--neon);
}

.benchmark-rows {
  color: var(--muted);
  font-size: 0.6rem;
  margin-top: 0.2rem;
}
""")
