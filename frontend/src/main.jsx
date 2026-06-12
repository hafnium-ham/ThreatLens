import React, { useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  AlertTriangle,
  BarChart3,
  Bell,
  ChevronDown,
  ChevronRight,
  ExternalLink,
  GitBranch,
  Play,
  Search,
  Shield,
  X,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import "./styles.css";

const API = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

const COLORS = {
  CRITICAL: "#ff3366",
  HIGH: "#ff8c00",
  MEDIUM: "#ffd700",
  LOW: "#00ff88",
  CLEAN: "#00ff88",
};

const LANG_COLORS = {
  JavaScript: "#ffd700",
  TypeScript: "#00d4ff",
  Python: "#3b82f6",
  Go: "#00d4ff",
  Rust: "#ff8c00",
  Java: "#ff3366",
  "C++": "#a78bfa",
  C: "#64748b",
};

function useApi(path, interval = 10000) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const load = async () => {
    try {
      const res = await fetch(`${API}${path}`);
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      setData(await res.json());
      setError("");
    } catch (err) {
      setError(err.message || "Request failed");
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => {
    load();
    const id = setInterval(load, interval);
    return () => clearInterval(id);
  }, [path, interval]);
  return { data, error, loading, reload: load };
}

function severityRank(value) {
  return { CRITICAL: 4, HIGH: 3, MEDIUM: 2, LOW: 1, CLEAN: 0 }[value] || 0;
}

function isFresh(date) {
  return Date.now() - new Date(date).getTime() < 24 * 60 * 60 * 1000;
}

function playAlarm() {
  const AudioContext = window.AudioContext || window.webkitAudioContext;
  if (!AudioContext) return;
  const ctx = new AudioContext();
  [0, 180, 360].forEach((offset) => {
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.frequency.value = 880;
    osc.type = "square";
    gain.gain.setValueAtTime(0.0001, ctx.currentTime + offset / 1000);
    gain.gain.exponentialRampToValueAtTime(0.08, ctx.currentTime + offset / 1000 + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + offset / 1000 + 0.13);
    osc.connect(gain).connect(ctx.destination);
    osc.start(ctx.currentTime + offset / 1000);
    osc.stop(ctx.currentTime + offset / 1000 + 0.16);
  });
}

function App() {
  const [username, setUsername] = useState("facebook");
  const [activeUser, setActiveUser] = useState("facebook");
  const [scan, setScan] = useState(null);
  const [scanStatus, setScanStatus] = useState(null);
  const [criticalAlerts, setCriticalAlerts] = useState(0);
  const [banner, setBanner] = useState(null);
  const [completeMessage, setCompleteMessage] = useState("");
  const repos = useApi(`/repos/${encodeURIComponent(activeUser)}`, 8000);
  const feed = useApi("/feed/live?limit=100", 12000);
  const previousCritical = useRef(new Set());

  useEffect(() => {
    const critical = [];
    for (const item of feed.data?.items || []) {
      if (item.severity === "CRITICAL") critical.push(item);
    }
    const next = new Set(critical.map((item) => `${item.vuln_id}:${item.repo_name}:${item.package_name}`));
    const newlySeen = critical.find((item) => !previousCritical.current.has(`${item.vuln_id}:${item.repo_name}:${item.package_name}`));
    if (previousCritical.current.size && newlySeen) {
      setCriticalAlerts((count) => count + 1);
      setBanner(`CRITICAL: ${newlySeen.vuln_id} affects ${newlySeen.repo_name} via ${newlySeen.package_name}`);
      playAlarm();
    }
    previousCritical.current = next;
  }, [feed.data]);

  useEffect(() => {
    if (criticalAlerts > 0) {
      document.title = `⚠ (${criticalAlerts}) CRITICAL | ThreatLens`;
    } else {
      document.title = "ThreatLens";
    }
  }, [criticalAlerts]);

  useEffect(() => {
    if (!scan?.scan_id) return;
    const wsUrl = `${API.replace(/^http/, "ws")}/ws/scan/${scan.scan_id}`;
    const socket = new WebSocket(wsUrl);
    socket.onmessage = (event) => {
      const message = JSON.parse(event.data);
      if (message.status) {
        setScanStatus((current) => ({ ...current, ...message }));
      }
      if (message.status === "complete") {
        setCompleteMessage(`COMPLETE: ${message.vulns_found || 0} vulns found`);
        repos.reload();
        feed.reload();
      }
    };
    return () => socket.close();
  }, [scan?.scan_id]);

  const scanGithub = async () => {
    setCompleteMessage("");
    const res = await fetch(`${API}/scan/github`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username }),
    });
    const payload = await res.json();
    setScan(payload);
    setScanStatus({ status: payload.status, repos_total: payload.repos_found || 0, repos_scanned: 0, vulns_found: 0 });
    setActiveUser(username);
  };

  return (
    <div className="app">
      {banner && (
        <div className="critical-banner">
          <AlertTriangle size={20} />
          <strong>{banner}</strong>
          <button onClick={() => setBanner(null)}><X size={18} /></button>
        </div>
      )}
      <header className="app-header">
        <div>
          <div className="brand">⬡ THREATLENS</div>
          <div className="subtitle">GitHub Repository Vulnerability Intelligence</div>
        </div>
        <div className="header-metrics">
          <span className="live-dot">● LIVE</span>
          <span className="critical-counter"><Bell size={15} /> {criticalAlerts} CRITICAL ALERTS</span>
          {completeMessage && <span className="complete-pill">{completeMessage}</span>}
        </div>
      </header>
      <main className="split-layout">
        <LiveFeed items={feed.data?.items || []} loading={feed.loading} error={feed.error} />
        <RepoIntelligence
          username={username}
          setUsername={setUsername}
          activeUser={activeUser}
          scanGithub={scanGithub}
          scanStatus={scanStatus}
          repos={repos.data?.items || []}
          analytics={repos.data?.analytics}
          loading={repos.loading}
          error={repos.error}
        />
      </main>
    </div>
  );
}

function LiveFeed({ items, loading, error }) {
  const tickerItems = items.length ? [...items, ...items] : [];
  return (
    <section className="left-panel">
      <div className="panel-title">⬡ LIVE VULNERABILITY FEED</div>
      {error && <div className="error">{error}</div>}
      {loading ? (
        <div className="scanline">INITIALIZING CVE STREAM</div>
      ) : (
        <div className="ticker-shell">
          <div className="ticker-list">
            {tickerItems.map((item, index) => (
              <article key={`${item.vuln_id}-${item.repo_name}-${index}`} className={`feed-entry ${item.severity === "CRITICAL" ? "critical" : ""}`}>
                <div className="feed-top">
                  <span className="cve">{item.vuln_id}</span>
                  <span className="severity-pill" style={{ background: COLORS[item.severity] }}>{item.severity}</span>
                </div>
                <div className="package-line">{item.package_name} {item.installed_version ? `@ ${item.installed_version}` : ""}</div>
                <div className="cvss" style={{ color: COLORS[item.severity] }}>{Number(item.cvss_score || 0).toFixed(1)}</div>
                <p>{item.description}</p>
                <div className="feed-meta">
                  <span>{new Date(item.published_date).toLocaleDateString()}</span>
                  {isFresh(item.published_date) && <strong>NEW</strong>}
                </div>
              </article>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

function RepoIntelligence({ username, setUsername, activeUser, scanGithub, scanStatus, repos, analytics, loading, error }) {
  const [sort, setSort] = useState("vuln");
  const [filter, setFilter] = useState("ALL");
  const [expanded, setExpanded] = useState(null);
  const filtered = useMemo(() => {
    let items = repos.filter((repo) => {
      if (filter === "ALL") return true;
      if (filter === "CLEAN") return repo.vuln_count === 0;
      return repo.worst_severity === filter;
    });
    items = [...items].sort((a, b) => {
      if (sort === "severity") return severityRank(b.worst_severity) - severityRank(a.worst_severity);
      if (sort === "stars") return b.stars - a.stars;
      if (sort === "updated") return new Date(b.updated_at) - new Date(a.updated_at);
      return b.vuln_count - a.vuln_count;
    });
    return items;
  }, [repos, sort, filter]);
  const progress = scanStatus?.repos_total ? Math.round((scanStatus.repos_scanned / scanStatus.repos_total) * 100) : 0;
  return (
    <section className="right-panel">
      <section className="scan-box">
        <div className="input-row">
          <Search size={22} />
          <input value={username} onChange={(e) => setUsername(e.target.value)} placeholder="Enter GitHub username or org" />
          <button onClick={scanGithub}><Play size={17} /> SCAN</button>
        </div>
        <div className="status-row">
          <span>{scanStatus?.status === "scanning" ? `Scanning ${scanStatus.repos_total || "…"} repos...` : `Last scanned: live | ${analytics?.total_repos || repos.length} repos | ${analytics?.total_vulns || 0} vulns found`}</span>
          <div className="progress"><span style={{ width: `${progress}%` }} /></div>
        </div>
      </section>
      <section className="repo-section">
        <div className="repo-toolbar">
          <h2>Repo Intelligence: <span>{activeUser}</span></h2>
          <div className="controls">
            <label>Sort by:
              <select value={sort} onChange={(e) => setSort(e.target.value)}>
                <option value="vuln">Vuln Count</option>
                <option value="severity">Severity</option>
                <option value="stars">Stars</option>
                <option value="updated">Updated</option>
              </select>
            </label>
            {["ALL", "CRITICAL", "HIGH", "MEDIUM", "CLEAN"].map((item) => (
              <button key={item} className={filter === item ? "active-filter" : ""} onClick={() => setFilter(item)}>{item}</button>
            ))}
          </div>
        </div>
        {error && <div className="error">{error}</div>}
        {loading ? <div className="scanline">LOADING REPOSITORY INTELLIGENCE</div> : (
          <div className="repo-list">
            {filtered.map((repo) => (
              <RepoCard key={repo.repo_name} repo={repo} username={activeUser} expanded={expanded === repo.repo_name} onToggle={() => setExpanded(expanded === repo.repo_name ? null : repo.repo_name)} />
            ))}
          </div>
        )}
      </section>
      <AnalyticsBar analytics={analytics} />
    </section>
  );
}

function RepoCard({ repo, username, expanded, onToggle }) {
  const vulns = useApi(expanded ? `/repos/${encodeURIComponent(username)}/${encodeURIComponent(repo.repo_name)}/vulns` : "/health", 30000);
  const color = COLORS[repo.worst_severity] || COLORS.CLEAN;
  return (
    <article className={`repo-card ${repo.worst_severity === "CRITICAL" ? "critical-repo" : ""}`}>
      <div className="repo-main" onClick={onToggle}>
        {expanded ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
        <a href={repo.repo_url} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()}>{repo.repo_name}<ExternalLink size={13} /></a>
        <span className="language" style={{ borderColor: LANG_COLORS[repo.language] || "#64748b", color: LANG_COLORS[repo.language] || "#64748b" }}>{repo.language}</span>
        <span className="vuln-count" style={{ color }}>{repo.vuln_count}</span>
        <SeverityBar breakdown={repo.severity_breakdown} />
        <span className="stars">★ {repo.stars.toLocaleString()}</span>
        <span className="updated">{new Date(repo.updated_at).toLocaleDateString()}</span>
      </div>
      {expanded && (
        <div className="vuln-details">
          {(vulns.data?.items || []).map((vuln) => (
            <div key={`${vuln.vuln_id}-${vuln.package_name}`} className="vuln-row">
              <span className="severity-pill" style={{ background: COLORS[vuln.severity] }}>{vuln.severity}</span>
              <strong>{vuln.package_name}</strong>
              <code>{vuln.installed_version || "unknown"}</code>
              <span>{vuln.vuln_id}</span>
              <em>{vuln.recommendation}</em>
            </div>
          ))}
          {!vulns.data?.items?.length && <div className="clean-message">No vulnerable dependencies found.</div>}
        </div>
      )}
    </article>
  );
}

function SeverityBar({ breakdown = {} }) {
  const total = Object.values(breakdown).reduce((sum, value) => sum + value, 0) || 1;
  return (
    <div className="severity-bar">
      {[
        ["critical", "CRITICAL"],
        ["high", "HIGH"],
        ["medium", "MEDIUM"],
        ["low", "LOW"],
      ].map(([key, label]) => (
        <span key={key} style={{ width: `${((breakdown[key] || 0) / total) * 100}%`, background: COLORS[label] }} />
      ))}
    </div>
  );
}

function AnalyticsBar({ analytics }) {
  const severityData = Object.entries(analytics?.severity_counts || {}).map(([name, count]) => ({ name: name.toUpperCase(), count }));
  return (
    <section className="analytics-bar">
      <Stat label="Total repos scanned" value={analytics?.total_repos || 0} color="#00d4ff" />
      <Stat label="Total vulns found" value={analytics?.total_vulns || 0} color="#ffd700" />
      <Stat label="Critical count" value={analytics?.critical_count || 0} color="#ff3366" />
      <Stat label="Most affected repo" value={analytics?.most_affected_repo || "none"} color="#00ff88" />
      <div className="mini-chart">
        <ResponsiveContainer width="100%" height={110}>
          <BarChart data={severityData}>
            <XAxis dataKey="name" stroke="#64748b" tick={{ fontSize: 10 }} />
            <Tooltip contentStyle={{ background: "#111827", border: "1px solid #1f2937", color: "#e2e8f0" }} />
            <Bar dataKey="count">
              {severityData.map((row) => <Cell key={row.name} fill={COLORS[row.name]} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className="mini-chart">
        <ResponsiveContainer width="100%" height={110}>
          <LineChart data={analytics?.vulns_over_time || []}>
            <CartesianGrid stroke="#1f2937" />
            <XAxis dataKey="day" stroke="#64748b" tick={{ fontSize: 10 }} />
            <YAxis stroke="#64748b" allowDecimals={false} />
            <Tooltip contentStyle={{ background: "#111827", border: "1px solid #1f2937", color: "#e2e8f0" }} />
            <Line dataKey="count" stroke="#00ff88" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}

function Stat({ label, value, color }) {
  return (
    <div className="stat">
      <span>{label}</span>
      <strong style={{ color }}>{value}</strong>
    </div>
  );
}

createRoot(document.getElementById("root")).render(<App />);
