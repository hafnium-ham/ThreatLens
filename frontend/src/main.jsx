import React, { useEffect, useMemo, useRef, useState, Component } from "react";
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
  Loader,
  CheckCircle,
  Activity,
  Zap,
  Clock,
  Terminal,
} from "lucide-react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
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

/* ─── Error Boundary ──────────────────────────────────────── */
class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }
  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }
  render() {
    if (this.state.hasError) {
      return (
        <div className="error-boundary">
          <AlertTriangle size={24} />
          <div>
            <strong>COMPONENT FAULT DETECTED</strong>
            <p>{this.state.error?.message || "Unknown error"}</p>
            <button onClick={() => this.setState({ hasError: false, error: null })}>
              RETRY
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

/* ─── Hooks ───────────────────────────────────────────────── */
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

function useAgentStatus() {
  const [status, setStatus] = useState("idle");
  useEffect(() => {
    const poll = async () => {
      try {
        const res = await fetch(`${API}/agent/status`);
        if (res.ok) {
          const data = await res.json();
          setStatus(data.status || "idle");
        }
      } catch {
        setStatus("idle");
      }
    };
    poll();
    const id = setInterval(poll, 5000);
    return () => clearInterval(id);
  }, []);
  return status;
}

/* ─── Utils ───────────────────────────────────────────────── */
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

/* ─── Animated Counter ────────────────────────────────────── */
function AnimatedCounter({ value, duration = 600 }) {
  const [display, setDisplay] = useState(0);
  const prevRef = useRef(0);
  useEffect(() => {
    const from = prevRef.current;
    const to = value;
    if (from === to) return;
    const start = performance.now();
    const animate = (now) => {
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      setDisplay(Math.round(from + (to - from) * progress));
      if (progress < 1) requestAnimationFrame(animate);
      else prevRef.current = to;
    };
    requestAnimationFrame(animate);
  }, [value, duration]);
  return <>{display}</>;
}

/* ─── Toast System ────────────────────────────────────────── */
let toastId = 0;
function ToastContainer({ toasts, removeToast }) {
  return (
    <div className="toast-container">
      {toasts.map((t) => (
        <div key={t.id} className="toast toast-critical" onAnimationEnd={(e) => {
          if (e.animationName === "toastOut") removeToast(t.id);
        }}>
          <AlertTriangle size={16} />
          <span>{t.message}</span>
          <button onClick={() => removeToast(t.id)}><X size={14} /></button>
        </div>
      ))}
    </div>
  );
}

/* ─── Splash Screen ───────────────────────────────────────── */
function SplashScreen({ onDone }) {
  useEffect(() => {
    const timer = setTimeout(onDone, 1500);
    return () => clearTimeout(timer);
  }, [onDone]);
  return (
    <div className="splash-screen">
      <div className="splash-content">
        <div className="splash-icon">⬡</div>
        <div className="splash-text">INITIALIZING THREAT INTELLIGENCE...</div>
        <div className="splash-bar"><div className="splash-bar-fill" /></div>
        <div className="splash-sub">CONNECTING TO CVE DATABASES • LOADING AI MODELS • ESTABLISHING FEEDS</div>
      </div>
      <div className="splash-scanline" />
    </div>
  );
}

/* ─── App ─────────────────────────────────────────────────── */
function App() {
  const [splashDone, setSplashDone] = useState(false);
  const [username, setUsername] = useState("facebook");
  const [activeUser, setActiveUser] = useState("facebook");
  const [scan, setScan] = useState(null);
  const [scanStatus, setScanStatus] = useState(null);
  const [criticalAlerts, setCriticalAlerts] = useState(0);
  const [banner, setBanner] = useState(null);
  const [completeMessage, setCompleteMessage] = useState("");
  const [toasts, setToasts] = useState([]);
  const [agentRunning, setAgentRunning] = useState(false);
  const [agentResult, setAgentResult] = useState(null);

  const agentStatus = useAgentStatus();
  const repos = useApi(`/repos/${encodeURIComponent(activeUser)}`, 8000);
  const feed = useApi("/feed/live?limit=100", 12000);
  const analytics = useApi("/analytics/summary", 15000);
  const previousCritical = useRef(new Set());

  const addToast = (message) => {
    const id = ++toastId;
    setToasts((prev) => [...prev, { id, message }]);
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 5000);
  };

  const removeToast = (id) => setToasts((prev) => prev.filter((t) => t.id !== id));

  const totalThreats = (feed.data?.items || []).length;

  useEffect(() => {
    const critical = [];
    for (const item of feed.data?.items || []) {
      if (item.severity === "CRITICAL") critical.push(item);
    }
    const next = new Set(critical.map((item) => `${item.vuln_id}:${item.repo_name}:${item.package_name}`));
    const newlySeen = critical.filter((item) => !previousCritical.current.has(`${item.vuln_id}:${item.repo_name}:${item.package_name}`));
    if (previousCritical.current.size && newlySeen.length) {
      setCriticalAlerts((count) => count + newlySeen.length);
      const first = newlySeen[0];
      setBanner(`CRITICAL: ${first.vuln_id} affects ${first.repo_name} via ${first.package_name}`);
      playAlarm();
      newlySeen.forEach((item) => {
        addToast(`🚨 ${item.vuln_id} — ${item.package_name} in ${item.repo_name}`);
      });
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

  const triggerAgent = async () => {
    setAgentRunning(true);
    setAgentResult(null);
    try {
      const res = await fetch(`${API}/agent/trigger`, { method: "POST" });
      const data = await res.json();
      const count = data.threats_found || data.count || 0;
      setAgentResult(`COMPLETE: ${count} threats found`);
      feed.reload();
      setTimeout(() => setAgentResult(null), 5000);
    } catch {
      setAgentResult("AGENT ERROR");
      setTimeout(() => setAgentResult(null), 5000);
    } finally {
      setAgentRunning(false);
    }
  };

  if (!splashDone) {
    return <SplashScreen onDone={() => setSplashDone(true)} />;
  }

  return (
    <div className="app app-enter">
      {banner && (
        <div className="critical-banner">
          <AlertTriangle size={20} />
          <strong>{banner}</strong>
          <button onClick={() => setBanner(null)}><X size={18} /></button>
        </div>
      )}
      <header className="app-header">
        <div className="header-left">
          <div className="brand">
            ⬡ THREATLENS
            <span className={`agent-dot ${agentStatus === "running" ? "agent-running" : "agent-idle"}`} title={`Agent: ${agentStatus}`} />
          </div>
          <div className="subtitle">GitHub Repository Vulnerability Intelligence</div>
        </div>
        <div className="header-metrics">
          <span className="live-dot">● LIVE</span>
          <span className="threat-counter">
            <Shield size={15} /> <AnimatedCounter value={totalThreats} /> THREATS
          </span>
          <span className="critical-counter"><Bell size={15} /> {criticalAlerts} CRITICAL ALERTS</span>
          <button className="agent-trigger-btn" onClick={triggerAgent} disabled={agentRunning}>
            {agentRunning ? <><Loader size={15} className="spin" /> RUNNING...</> :
             agentResult ? <><CheckCircle size={15} /> {agentResult}</> :
             <><Zap size={15} /> RUN AGENT NOW</>}
          </button>
          {completeMessage && <span className="complete-pill">{completeMessage}</span>}
        </div>
      </header>
      <main className="split-layout">
        <ErrorBoundary>
          <LiveFeed items={feed.data?.items || []} loading={feed.loading} error={feed.error} />
        </ErrorBoundary>
        <ErrorBoundary>
          <RepoIntelligence
            username={username}
            setUsername={setUsername}
            activeUser={activeUser}
            scanGithub={scanGithub}
            scanStatus={scanStatus}
            repos={repos.data?.items || []}
            analytics={repos.data?.analytics}
            analyticsExtra={analytics.data}
            loading={repos.loading}
            error={repos.error}
          />
        </ErrorBoundary>
      </main>
      <ToastContainer toasts={toasts} removeToast={removeToast} />
    </div>
  );
}

/* ─── Live Feed ───────────────────────────────────────────── */
function LiveFeed({ items, loading, error }) {
  const [severityFilter, setSeverityFilter] = useState("ALL");
  const [sourceFilter, setSourceFilter] = useState("ALL");
  const [expandedId, setExpandedId] = useState(null);
  const [paused, setPaused] = useState(false);

  const filteredItems = useMemo(() => {
    return items.filter((item) => {
      if (severityFilter !== "ALL" && item.severity !== severityFilter) return false;
      if (sourceFilter !== "ALL") {
        const src = (item.source || item.username || "").toUpperCase();
        if (!src.includes(sourceFilter)) return false;
      }
      return true;
    });
  }, [items, severityFilter, sourceFilter]);

  const tickerItems = filteredItems.length ? [...filteredItems, ...filteredItems] : [];

  const handleEntryClick = (key) => {
    setExpandedId(expandedId === key ? null : key);
    setPaused(true);
  };

  return (
    <section className="left-panel">
      <div className="panel-title">⬡ LIVE VULNERABILITY FEED</div>
      <div className="feed-filters">
        <div className="filter-group">
          {["ALL", "CRITICAL", "HIGH", "MEDIUM", "LOW"].map((s) => (
            <button key={s} className={severityFilter === s ? "active-filter" : ""} onClick={() => setSeverityFilter(s)}
              style={s !== "ALL" ? { borderColor: COLORS[s], color: severityFilter === s ? "#0a0e1a" : COLORS[s], background: severityFilter === s ? COLORS[s] : "transparent" } : {}}>
              {s}
            </button>
          ))}
        </div>
        <div className="filter-group">
          {["ALL", "NVD", "SHODAN", "GITHUB", "HIBP"].map((s) => (
            <button key={s} className={sourceFilter === s ? "active-filter" : ""} onClick={() => setSourceFilter(s)}>{s}</button>
          ))}
        </div>
      </div>
      {error && <div className="error">{error}</div>}
      {loading ? (
        <div className="scanline">INITIALIZING CVE STREAM</div>
      ) : (
        <div className="ticker-shell" onMouseEnter={() => setPaused(true)} onMouseLeave={() => { if (!expandedId) setPaused(false); }}>
          <div className={`ticker-list ${paused ? "ticker-paused" : ""}`}>
            {tickerItems.map((item, index) => {
              const key = `${item.vuln_id}-${item.repo_name}-${index}`;
              const isExpanded = expandedId === key;
              return (
                <article key={key} className={`feed-entry ${item.severity === "CRITICAL" ? "critical" : ""} ${isExpanded ? "feed-expanded" : ""}`}
                  onClick={() => handleEntryClick(key)}>
                  <div className="feed-top">
                    <span className="cve">{item.vuln_id}</span>
                    <span className="severity-pill" style={{ background: COLORS[item.severity] }}>{item.severity}</span>
                  </div>
                  <div className="package-line">{item.package_name} {item.installed_version ? `@ ${item.installed_version}` : ""}</div>
                  <div className="cvss-row">
                    <span className="cvss" style={{ color: COLORS[item.severity] }}>{Number(item.cvss_score || 0).toFixed(1)}</span>
                    <div className="cvss-bar-track">
                      <div className="cvss-bar-fill" style={{ width: `${(Number(item.cvss_score || 0) / 10) * 100}%`, background: COLORS[item.severity] }} />
                    </div>
                  </div>
                  <p>{item.description}</p>
                  <div className="feed-meta">
                    <span>{new Date(item.published_date).toLocaleDateString()}</span>
                    {isFresh(item.published_date) && <strong>NEW</strong>}
                  </div>
                  {isExpanded && (
                    <div className="feed-expanded-details">
                      {item.ai_summary && <div className="ai-summary"><strong>AI ANALYSIS:</strong> {item.ai_summary}</div>}
                      <div className="expanded-meta">
                        <span><strong>Published:</strong> {new Date(item.published_date).toLocaleString()}</span>
                        {item.package_name && <span><strong>Package:</strong> {item.package_name}</span>}
                        {item.installed_version && <span><strong>Version:</strong> {item.installed_version}</span>}
                        {item.fixed_version && <span><strong>Fix:</strong> {item.fixed_version}</span>}
                        {item.langfuse_trace_id && (
                          <a href={`https://cloud.langfuse.com/trace/${item.langfuse_trace_id}`} target="_blank" rel="noreferrer" className="trace-link">
                            <ExternalLink size={12} /> Langfuse Trace
                          </a>
                        )}
                      </div>
                    </div>
                  )}
                </article>
              );
            })}
          </div>
        </div>
      )}
    </section>
  );
}

/* ─── Repo Intelligence ───────────────────────────────────── */
function RepoIntelligence({ username, setUsername, activeUser, scanGithub, scanStatus, repos, analytics, analyticsExtra, loading, error }) {
  const [sort, setSort] = useState("vuln");
  const [filter, setFilter] = useState("ALL");
  const [expanded, setExpanded] = useState(null);

  const filterCounts = useMemo(() => {
    const counts = { ALL: repos.length, CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 0, CLEAN: 0 };
    repos.forEach((repo) => {
      if (repo.vuln_count === 0) counts.CLEAN++;
      else if (repo.worst_severity) counts[repo.worst_severity] = (counts[repo.worst_severity] || 0) + 1;
    });
    return counts;
  }, [repos]);

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
            {["ALL", "CRITICAL", "HIGH", "MEDIUM", "LOW", "CLEAN"].map((item) => (
              <button key={item} className={filter === item ? "active-filter" : ""} onClick={() => setFilter(item)}>
                {item} <span className="filter-count">{filterCounts[item] || 0}</span>
              </button>
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
      <ErrorBoundary>
        <AnalyticsBar analytics={analytics} analyticsExtra={analyticsExtra} />
      </ErrorBoundary>
    </section>
  );
}

/* ─── Repo Card ───────────────────────────────────────────── */
function RepoCard({ repo, username, expanded, onToggle }) {
  const vulns = useApi(expanded ? `/repos/${encodeURIComponent(username)}/${encodeURIComponent(repo.repo_name)}/vulns` : "/health", 30000);
  const color = COLORS[repo.worst_severity] || COLORS.CLEAN;

  const mostCritical = useMemo(() => {
    if (!expanded || !vulns.data?.items?.length) return null;
    const sorted = [...vulns.data.items].sort((a, b) => severityRank(b.severity) - severityRank(a.severity));
    return sorted[0];
  }, [expanded, vulns.data]);

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
          {mostCritical && (
            <div className="fix-priority">
              <AlertTriangle size={14} />
              FIX FIRST: <strong>{mostCritical.vuln_id}</strong> — {mostCritical.package_name} ({mostCritical.severity})
            </div>
          )}
          <a href={repo.repo_url} target="_blank" rel="noreferrer" className="github-link-btn" onClick={(e) => e.stopPropagation()}>
            <GitBranch size={14} /> View on GitHub <ExternalLink size={12} />
          </a>
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

/* ─── Severity Bar ────────────────────────────────────────── */
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

/* ─── Custom Donut Center Label ───────────────────────────── */
function DonutCenterLabel({ viewBox, value }) {
  const { cx, cy } = viewBox;
  return (
    <text x={cx} y={cy} textAnchor="middle" dominantBaseline="central" fill="#e2e8f0" fontFamily="JetBrains Mono, monospace" fontWeight="900" fontSize="18">
      {value}
    </text>
  );
}

/* ─── Analytics Bar ───────────────────────────────────────── */
function AnalyticsBar({ analytics, analyticsExtra }) {
  const severityData = Object.entries(analytics?.severity_counts || {}).map(([name, count]) => ({ name: name.toUpperCase(), count }));
  const totalSeverity = severityData.reduce((sum, d) => sum + d.count, 0);

  const meanTriageTime = analyticsExtra?.mean_triage_time_ms || analyticsExtra?.avg_ai_latency_ms || null;
  const threatVelocity = analyticsExtra?.threat_velocity || null;
  const queryBenchmarks = analyticsExtra?.query_benchmarks || null;

  return (
    <section className="analytics-bar">
      <Stat label="Total repos scanned" value={analytics?.total_repos || 0} color="#00d4ff" />
      <Stat label="Total vulns found" value={analytics?.total_vulns || 0} color="#ffd700" />
      <Stat label="Critical count" value={analytics?.critical_count || 0} color="#ff3366" />
      <Stat label="Most affected repo" value={analytics?.most_affected_repo || "none"} color="#00ff88" />
      {meanTriageTime !== null && (
        <Stat label="Mean Time to Triage" value={`${Math.round(meanTriageTime)}ms`} color="#00d4ff" icon={<Clock size={14} />} />
      )}
      {threatVelocity && (
        <div className="stat threat-velocity">
          <span><Activity size={12} /> Threat Velocity</span>
          <strong style={{ color: "#00ff88" }}>{threatVelocity.current || 0}/hr</strong>
          <div className="velocity-compare">
            vs <span style={{ color: "#64748b" }}>{threatVelocity.previous_24h || 0}/hr</span> 24h ago
          </div>
        </div>
      )}
      <div className="mini-chart">
        <ResponsiveContainer width="100%" height={130}>
          <PieChart>
            <Pie data={severityData} dataKey="count" nameKey="name" cx="50%" cy="50%" innerRadius={32} outerRadius={52} paddingAngle={3} strokeWidth={0}>
              {severityData.map((row) => <Cell key={row.name} fill={COLORS[row.name] || "#64748b"} />)}
            </Pie>
            <Pie data={[{ value: 1 }]} dataKey="value" cx="50%" cy="50%" innerRadius={0} outerRadius={0} fill="transparent">
              <Cell fill="transparent" />
            </Pie>
            <Tooltip contentStyle={{ background: "#111827", border: "1px solid #1f2937", color: "#e2e8f0", fontFamily: "JetBrains Mono, monospace" }} />
            <text x="50%" y="50%" textAnchor="middle" dominantBaseline="central" fill="#e2e8f0" style={{ fontFamily: "JetBrains Mono, monospace", fontWeight: 900, fontSize: "16px" }}>
              {totalSeverity}
            </text>
          </PieChart>
        </ResponsiveContainer>
      </div>
      <div className="mini-chart">
        <ResponsiveContainer width="100%" height={130}>
          <AreaChart data={analytics?.vulns_over_time || []}>
            <defs>
              <linearGradient id="neonGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#00ff88" stopOpacity={0.4} />
                <stop offset="100%" stopColor="#00ff88" stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="#1f2937" />
            <XAxis dataKey="day" stroke="#64748b" tick={{ fontSize: 10 }} />
            <YAxis stroke="#64748b" allowDecimals={false} />
            <Tooltip contentStyle={{ background: "#111827", border: "1px solid #1f2937", color: "#e2e8f0" }} />
            <Area type="monotone" dataKey="count" stroke="#00ff88" strokeWidth={2} fill="url(#neonGrad)" dot={false} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
      {queryBenchmarks && queryBenchmarks.length > 0 && (
        <div className="benchmark-panel">
          <div className="benchmark-title"><Terminal size={14} /> CLICKHOUSE QUERY BENCHMARK</div>
          <div className="benchmark-grid">
            {queryBenchmarks.slice(0, 3).map((q, i) => (
              <div key={i} className="benchmark-card">
                <div className="benchmark-query">{q.query || q.name || `Query ${i + 1}`}</div>
                <div className="benchmark-time">EXECUTED IN <strong>{q.execution_time_ms || q.time_ms || 0}ms</strong></div>
                {q.rows_read && <div className="benchmark-rows">{q.rows_read.toLocaleString()} rows</div>}
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

/* ─── Stat ────────────────────────────────────────────────── */
function Stat({ label, value, color, icon }) {
  return (
    <div className="stat">
      <span>{icon} {label}</span>
      <strong style={{ color }}>{value}</strong>
    </div>
  );
}

createRoot(document.getElementById("root")).render(<App />);
