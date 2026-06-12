import re

with open("frontend/src/styles.css", "r") as f:
    content = f.read()

# Remove split-layout
content = re.sub(r'/\* ─── Main Areas ─── \*/.*?\.feed-filters \{.*?\n\}', '', content, flags=re.DOTALL)

# Remove ticker-shell, ticker-list, etc.
content = re.sub(r'\.ticker-shell \{.*?\n\}', '', content, flags=re.DOTALL)
content = re.sub(r'\.ticker-list \{.*?\n\}', '', content, flags=re.DOTALL)
content = re.sub(r'\.ticker-paused \{.*?\n\}', '', content, flags=re.DOTALL)
content = re.sub(r'@keyframes ticker \{.*?\n\}', '', content, flags=re.DOTALL)

# Add new styles
new_styles = """
/* ─── CVE Feed Items ───────────────────────────────────────── */
.feed-card {
  border-radius: 0 4px 4px 0;
  display: grid;
  grid-template-rows: auto auto auto auto;
  padding: 8px 10px;
  cursor: pointer;
  border-bottom: 1px solid var(--border);
  background: rgba(10, 14, 26, 0.6);
  transition: background 0.15s;
}

.feed-card:hover {
  background: rgba(10, 14, 26, 0.9);
}

.feed-card .feed-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.2rem;
}

.feed-card .cve {
  color: var(--cyan);
  font-weight: 700;
  font-size: 0.75rem;
}

.feed-card .cvss-pill {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  font-weight: 900;
  font-size: 0.7rem;
  color: #0a0e1a;
}

.feed-card .package-line {
  color: var(--muted);
  font-family: "JetBrains Mono", monospace;
  font-size: 0.7rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 0.3rem;
}

.feed-card p {
  color: var(--muted);
  font-size: 11px;
  margin: 0 0 0.3rem 0;
  white-space: normal;
  overflow: hidden;
  text-overflow: ellipsis;
}

.feed-card .feed-meta {
  font-size: 0.65rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 0.3rem;
}

.feed-card.expanded {
  background: #080d18;
}

/* ─── Tabs ─────────────────────────────────────────────────── */
.tab-bar {
  display: flex;
  flex-direction: row;
  height: 40px;
  border-bottom: 1px solid var(--border);
  background: #050a12;
  position: sticky;
  top: 0;
  z-index: 10;
}

.tab-btn {
  width: 120px;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  color: var(--muted);
  font-size: 0.75rem;
  font-weight: 700;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  transition: all 0.2s;
  font-family: "JetBrains Mono", monospace;
}

.tab-btn:hover {
  color: var(--text);
  background: rgba(255, 255, 255, 0.02);
}

.tab-btn.active {
  color: var(--neon);
  border-bottom: 2px solid var(--neon);
  background: rgba(0, 255, 136, 0.05);
}

.tab-content {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.agent-log-table {
  width: 100%;
  border-collapse: collapse;
}

.agent-log-table th, .agent-log-table td {
  padding: 0.6rem;
  text-align: left;
  border-bottom: 1px solid var(--border);
  font-family: "JetBrains Mono", monospace;
  font-size: 0.75rem;
}

.agent-log-table th {
  color: var(--muted);
}
"""
content += new_styles

with open("frontend/src/styles.css", "w") as f:
    f.write(content)
