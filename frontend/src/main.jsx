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

// Use configured API base if provided at build time; otherwise use relative origin so the SPA works when served from the same host
const API = import.meta.env.VITE_API_BASE_URL ?? "";
// Helper to resolve websocket base depending on runtime environment
function wsBaseFor(apiBase) {
  if (apiBase) return apiBase.replace(/^http/, "ws");
  const proto = location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${location.host}`;
}

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
          setStatus(data.running ? "running" : "idle");
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

function getCvssColor(score) {
  if (score >= 9) return COLORS.CRITICAL;
  if (score >= 7) return COLORS.HIGH;
  if (score >= 4) return COLORS.MEDIUM;
  return COLORS.LOW;
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
  const [activeTab, setActiveTab] = useState("repos");

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
    const wsUrl = `${wsBaseFor(API)}/ws/scan/${scan.scan_id}`;
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
    const resolved = payload.resolved_username || username;
    setScan(payload);
    setScanStatus({ status: payload.status, repos_total: payload.repos_found || 0, repos_scanned: 0, vulns_found: 0 });
    setUsername(resolved);
    setActiveUser(resolved);
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
    <div className={`app-shell app-enter ${agentRunning ? "agent-active" : ""}`}>
      {banner && (
        <div className="critical-banner" style={{ position: "absolute", top: 48, left: 0, right: 0, zIndex: 50 }}>
          <AlertTriangle size={20} />
          <strong>{banner}</strong>
          <button onClick={() => setBanner(null)}><X size={18} /></button>
        </div>
      )}
      
      {/* ZONE 1 - HEADER */}
      <header className="header">
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
          <button className={`agent-trigger-btn ${agentRunning ? "running" : ""}`} onClick={triggerAgent} disabled={agentRunning}>
            {agentRunning ? <><Loader size={15} className="spin" /> AI AGENT ACTIVE - SCANNING...</> :
             agentResult ? <><CheckCircle size={15} /> {agentResult}</> :
             <><Zap size={15} /> RUN AGENT NOW</>}
          </button>
          {completeMessage && <span className="complete-pill">{completeMessage}</span>}
        </div>
      </header>

      {/* ZONE 2 - LEFT PANEL */}
      <aside className="left-panel">
        <ErrorBoundary>
          <LiveFeed items={feed.data?.items || []} loading={feed.loading} error={feed.error} />
        </ErrorBoundary>
      </aside>

      {/* ZONE 3 - MAIN AREA */}
      <main className="main-area">
        <div className="tab-bar">
          <button className={`tab-btn ${activeTab === "repos" ? "active" : ""}`} onClick={() => setActiveTab("repos")}>REPOS</button>
          <button className={`tab-btn ${activeTab === "analytics" ? "active" : ""}`} onClick={() => setActiveTab("analytics")}>ANALYTICS</button>
          <button className={`tab-btn ${activeTab === "agent_log" ? "active" : ""}`} onClick={() => setActiveTab("agent_log")}>AGENT LOG</button>
          <button className={`tab-btn ${activeTab === "cve_intel" ? "active" : ""}`} onClick={() => setActiveTab("cve_intel")}>CVE INTEL</button>
        </div>
        
        <div className="tab-content">
          <ErrorBoundary>
            {activeTab === "repos" && (
              <RepoIntelligenceTab
                username={username}
                setUsername={setUsername}
                activeUser={activeUser}
                scanGithub={scanGithub}
                scanStatus={scanStatus}
                repos={repos.data?.items || []}
                loading={repos.loading}
                error={repos.error}
              />
            )}
            {activeTab === "analytics" && (
              <AnalyticsTab
                analytics={repos.data?.analytics}
                analyticsExtra={analytics.data}
              />
            )}
            {activeTab === "agent_log" && <AgentLogTab />}
            {activeTab === "cve_intel" && <CveIntelTab />}
          </ErrorBoundary>
        </div>
      </main>

      <ToastContainer toasts={toasts} removeToast={removeToast} />
    </div>
  );
}

/* ─── Zone 2: Live Feed ────────────────────────────────────── */
function LiveFeed({ items, loading, error }) {
  const [severityFilter, setSeverityFilter] = useState("ALL");
  const [sourceFilter, setSourceFilter] = useState("ALL");
  const [expandedId, setExpandedId] = useState(null);

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

  const handleEntryClick = (key) => {
    setExpandedId(expandedId === key ? null : key);
  };

  return (
    <>
      <div style={{ fontSize: '11px', color: 'var(--muted)', letterSpacing: '0.1em', marginBottom: '0.5rem', padding: '0.5rem' }}>CVE FEED</div>
      <div className="feed-filters">
        <div className="filter-group" style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
          {["ALL", "CRITICAL", "HIGH", "MEDIUM", "LOW"].map((s) => (
            <button key={s} className={severityFilter === s ? "active-filter" : ""} onClick={() => setSeverityFilter(s)}
              style={{ fontSize: '10px', padding: '2px 6px', ...(s !== "ALL" ? { borderColor: COLORS[s], color: severityFilter === s ? "#0a0e1a" : COLORS[s], background: severityFilter === s ? COLORS[s] : "transparent" } : {})}}>
              {s}
            </button>
          ))}
        </div>
        <div className="filter-group" style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
          {["ALL", "NVD", "SHODAN", "GITHUB", "HIBP"].map((s) => (
            <button key={s} className={sourceFilter === s ? "active-filter" : ""} onClick={() => setSourceFilter(s)}
              style={{ fontSize: '10px', padding: '2px 6px' }}>{s}</button>
          ))}
        </div>
      </div>
      {error && <div className="error">{error}</div>}
      {loading ? (
        <div className="scanline">INITIALIZING CVE STREAM</div>
      ) : (
        <div className="feed-list" style={{ flex: 1 }}>
          {filteredItems.map((item, index) => {
            const key = `${item.vuln_id}-${item.repo_name}-${index}`;
            const isExpanded = expandedId === key;
            const cvssColor = getCvssColor(Number(item.cvss_score || 0));
            return (
              <article key={key} className={`feed-card ${isExpanded ? "expanded" : ""}`}
                style={{ borderLeftColor: COLORS[item.severity] }}
                onClick={() => handleEntryClick(key)}>
                <div className="feed-top">
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <div className="cvss-pill" style={{ background: cvssColor }}>{Number(item.cvss_score || 0).toFixed(1)}</div>
                    <span className="cve">{item.vuln_id}</span>
                  </div>
                  <span className="severity-pill" style={{ background: COLORS[item.severity], padding: '2px 6px', fontSize: '9px' }}>{item.severity}</span>
                </div>
                <div className="package-line">{item.package_name} {item.installed_version ? `@ ${item.installed_version}` : ""}</div>
                <p>{item.description}</p>
                <div className="feed-meta">
                  <span>{new Date(item.published_date).toLocaleDateString()}</span>
                  {isFresh(item.published_date) && <strong style={{ color: 'var(--neon)' }}>NEW</strong>}
                </div>
                {isExpanded && (
                  <div className="feed-expanded-details" style={{ marginTop: '0.5rem', paddingTop: '0.5rem', borderTop: '1px solid var(--border)' }}>
                    {item.ai_summary && <div className="ai-summary" style={{ fontSize: '0.75rem', marginBottom: '0.5rem' }}><strong>AI ANALYSIS:</strong> {item.ai_summary}</div>}
                    <div className="expanded-meta" style={{ fontSize: '0.7rem', display: 'flex', flexDirection: 'column', gap: '0.3rem' }}>
                      {item.package_name && <span><strong>Package:</strong> {item.package_name}</span>}
                      {item.installed_version && <span><strong>Version:</strong> {item.installed_version}</span>}
                      {item.fixed_version && <span><strong>Fix:</strong> {item.fixed_version}</span>}
                      {item.langfuse_trace_id && (
                        <a href={`https://cloud.langfuse.com/trace/${item.langfuse_trace_id}`} target="_blank" rel="noreferrer" className="trace-link" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', color: 'var(--cyan)', marginTop: '4px' }}>
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
      )}
    </>
  );
}

/* ─── Zone 3: RepoIntelligence Tab ────────────────────────── */
function RepoIntelligenceTab({ username, setUsername, activeUser, scanGithub, scanStatus, repos, loading, error }) {
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
    <>
      <section className="scan-box">
        <div className="input-row">
          <Search size={22} />
          <input value={username} onChange={(e) => setUsername(e.target.value)} placeholder="Enter GitHub username or org" />
          <button onClick={scanGithub}><Play size={17} /> SCAN</button>
        </div>
        <div className="status-row">
          <span>{scanStatus?.status === "scanning" ? `Scanning ${scanStatus.repos_total || "…"} repos...` : `Last scanned: live | ${repos.length} repos`}</span>
          <div className="progress"><span style={{ width: `${progress}%` }} /></div>
        </div>
      </section>
      <section className="repo-section" style={{ flex: 1 }}>
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
    </>
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

/* ─── Threat Sources Chart ────────────────────────────────────── */
function ThreatSourcesChart({ data }) {
  if (!data || data.length === 0) return null;
  return (
    <div className="threat-map-container" style={{ padding: '1rem', border: '1px solid var(--border)', borderRadius: '0.55rem', background: 'rgba(17, 24, 39, 0.92)' }}>
      <div className="benchmark-title" style={{ marginBottom: '1rem' }}><Activity size={14} /> THREAT SOURCES</div>
      <div style={{ height: '250px' }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical" margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" horizontal={false} />
            <XAxis type="number" stroke="#64748b" />
            <YAxis dataKey="source" type="category" stroke="#64748b" width={80} />
            <Tooltip contentStyle={{ background: "#111827", border: "1px solid #1f2937", color: "#e2e8f0" }} />
            <Bar dataKey="count" fill="var(--cyan)" radius={[0, 4, 4, 0]}>
              {data.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={index === 0 ? "var(--neon)" : "var(--cyan)"} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

/* ─── Zone 3: Analytics Tab ───────────────────────────────── */
function AnalyticsTab({ analytics, analyticsExtra }) {
  const severityData = Object.entries(analytics?.severity_counts || {}).map(([name, count]) => ({ name: name.toUpperCase(), count }));
  const totalSeverity = severityData.reduce((sum, d) => sum + d.count, 0);

  const meanTriageTime = analyticsExtra?.mean_time_to_triage_ms ?? null;
  const threatVelocity = analyticsExtra?.threat_velocity || null;
  const queryBenchmarks = analyticsExtra?.query_benchmarks || null;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Row 1: 4 Stats */}
      <div style={{ display: 'flex', gap: '1rem' }}>
        <div style={{ flex: 1 }}><Stat label="Total repos scanned" value={analytics?.total_repos || 0} color="#00d4ff" /></div>
        <div style={{ flex: 1 }}><Stat label="Total vulns found" value={analytics?.total_vulns || 0} color="#ffd700" /></div>
        <div style={{ flex: 1 }}><Stat label="Critical count" value={analytics?.critical_count || 0} color="#ff3366" /></div>
        <div style={{ flex: 1 }}><Stat label="Most affected repo" value={analytics?.most_affected_repo || "none"} color="#00ff88" /></div>
      </div>

      {/* Row 2: 3 Stats */}
      <div style={{ display: 'flex', gap: '1rem' }}>
        <div style={{ flex: 1 }}>
          <Stat label="Mean Time to Triage" value={meanTriageTime !== null ? `${Math.round(meanTriageTime)}ms` : "-"} color="#00d4ff" icon={<Clock size={14} />} />
        </div>
        <div style={{ flex: 1 }} className="stat threat-velocity">
          <span><Activity size={12} /> Threat Velocity</span>
          <strong style={{ color: "#00ff88" }}>{threatVelocity?.current_hour || 0}/hr</strong>
          <div className="velocity-compare">
            vs <span style={{ color: "#64748b" }}>{threatVelocity?.same_hour_24h_ago || 0}/hr</span> 24h ago
          </div>
        </div>
        <div style={{ flex: 1 }}>
           <Stat label="Active Scans" value="0" color="#a78bfa" icon={<Terminal size={14} />} />
        </div>
      </div>

      {/* Row 3: Charts */}
      <div style={{ display: 'flex', gap: '1rem' }}>
        <div className="mini-chart" style={{ flex: 1, minHeight: '200px' }}>
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie data={severityData} dataKey="count" nameKey="name" cx="50%" cy="50%" innerRadius={50} outerRadius={80} paddingAngle={3} strokeWidth={0}>
                {severityData.map((row) => <Cell key={row.name} fill={COLORS[row.name] || "#64748b"} />)}
              </Pie>
              <Tooltip contentStyle={{ background: "#111827", border: "1px solid #1f2937", color: "#e2e8f0", fontFamily: "JetBrains Mono, monospace" }} />
              <text x="50%" y="50%" textAnchor="middle" dominantBaseline="central" fill="#e2e8f0" style={{ fontFamily: "JetBrains Mono, monospace", fontWeight: 900, fontSize: "24px" }}>
                {totalSeverity}
              </text>
            </PieChart>
          </ResponsiveContainer>
        </div>
        <div className="mini-chart" style={{ flex: 1, minHeight: '200px' }}>
          <ResponsiveContainer width="100%" height={200}>
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
      </div>

      {/* Row 4: Benchmarks */}
      {queryBenchmarks && queryBenchmarks.length > 0 && (
        <div className="benchmark-panel">
          <div className="benchmark-title"><Terminal size={14} /> CLICKHOUSE QUERY BENCHMARK</div>
          <div className="benchmark-grid">
            {queryBenchmarks.slice(0, 3).map((q, i) => (
              <div key={i} className="benchmark-card">
                <div className="benchmark-query">{q.name || `Query ${i + 1}`}</div>
                <div className="benchmark-time">EXECUTED IN <strong>{q.execution_ms || 0}ms</strong></div>
                {q.result && <div className="benchmark-rows">{q.result.length.toLocaleString()} rows returned</div>}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Row 5: Threat Sources */}
      <ThreatSourcesChart data={analyticsExtra?.by_source} />
    </div>
  );
}

/* ─── Stat ────────────────────────────────────────────────── */
function Stat({ label, value, color, icon }) {
  return (
    <div className="stat" style={{ height: '100%' }}>
      <span>{icon} {label}</span>
      <strong style={{ color }}>{value}</strong>
    </div>
  );
}

/* ─── Zone 3: Agent Log Tab ───────────────────────────────── */
function AgentLogTab() {
  const { data, loading, error } = useApi("/agent/runs");
  
  if (loading) return <div className="scanline">LOADING AGENT LOGS...</div>;
  if (error) return <div className="error">{error}</div>;

  const runs = data?.items || [];
  
  return (
    <div>
      <h2 style={{ fontSize: '1rem', color: 'var(--neon)', fontFamily: '"JetBrains Mono", monospace', marginBottom: '1rem' }}>Autonomous Agent Run Log</h2>
      <table className="agent-log-table">
        <thead>
          <tr>
            <th>TIMESTAMP</th>
            <th>RUN ID</th>
            <th>DURATION</th>
            <th>THREATS</th>
            <th>MODEL</th>
            <th>TRACE</th>
          </tr>
        </thead>
        <tbody>
          {runs.map(run => (
            <tr key={run.id}>
              <td>{new Date(run.timestamp).toLocaleString()}</td>
              <td style={{ color: 'var(--cyan)' }}>{run.id.substring(0, 8)}</td>
              <td>{run.duration_ms}ms</td>
              <td><span className="severity-pill" style={{ background: run.threats_found > 0 ? 'var(--critical)' : 'var(--neon)' }}>{run.threats_found}</span></td>
              <td>{run.model_used}</td>
              <td>
                {run.langfuse_trace_id && data.langfuse_host ? (
                  <a href={`${data.langfuse_host}/trace/${run.langfuse_trace_id}`} target="_blank" rel="noreferrer" style={{ color: 'var(--cyan)', textDecoration: 'none' }}>
                    View Trace <ExternalLink size={10} />
                  </a>
                ) : "-"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ─── Zone 3: CVE Intel Tab ───────────────────────────────── */
function CveIntelTab() {
  const [search, setSearch] = useState("");
  const { data, loading, error } = useApi(`/cves?search=${encodeURIComponent(search)}`);
  
  return (
    <div>
      <div className="input-row" style={{ marginBottom: '1.5rem' }}>
        <Search size={22} />
        <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search CVE ID, package name, or description" style={{ width: '400px' }} />
      </div>
      
      {loading ? <div className="scanline">SEARCHING CVE DATABASES...</div> : error ? <div className="error">{error}</div> : (
        <table className="agent-log-table">
          <thead>
            <tr>
              <th>CVE ID</th>
              <th>PACKAGE</th>
              <th>CVSS</th>
              <th>SEVERITY</th>
              <th>PUBLISHED</th>
              <th>AI NOTES</th>
            </tr>
          </thead>
          <tbody>
            {(data?.items || []).map(cve => (
              <tr key={cve.cve_id}>
                <td style={{ color: 'var(--cyan)' }}>{cve.cve_id}</td>
                <td>{(cve.affected_products || []).join(", ")}</td>
                <td style={{ color: getCvssColor(cve.cvss_score) }}>{Number(cve.cvss_score).toFixed(1)}</td>
                <td><span className="severity-pill" style={{ background: getCvssColor(cve.cvss_score) }}>{cve.cvss_score >= 9 ? 'CRITICAL' : cve.cvss_score >= 7 ? 'HIGH' : cve.cvss_score >= 4 ? 'MEDIUM' : 'LOW'}</span></td>
                <td>{new Date(cve.published_date).toLocaleDateString()}</td>
                <td style={{ maxWidth: '300px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }} title={cve.ai_triage_notes}>{cve.ai_triage_notes}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

createRoot(document.getElementById("root")).render(<App />);
