CREATE DATABASE IF NOT EXISTS threatlens;

CREATE TABLE IF NOT EXISTS threatlens.threat_events
(
    id String,
    timestamp DateTime64(3, 'UTC'),
    source LowCardinality(String),
    threat_type LowCardinality(String),
    target String,
    severity UInt8,
    raw_data String,
    ai_summary String,
    status LowCardinality(String),
    triage_latency_ms UInt32 DEFAULT 0,
    langfuse_trace_id String DEFAULT ''
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, severity, source, id)
TTL toDateTime(timestamp) + INTERVAL 365 DAY;

CREATE TABLE IF NOT EXISTS threatlens.agent_runs
(
    id String,
    timestamp DateTime64(3, 'UTC'),
    duration_ms UInt32,
    threats_found UInt32,
    model_used LowCardinality(String),
    langfuse_trace_id String,
    status LowCardinality(String) DEFAULT 'success',
    severity_breakdown String DEFAULT '{}'
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, id);

CREATE TABLE IF NOT EXISTS threatlens.cve_intel
(
    cve_id String,
    published_date DateTime64(3, 'UTC'),
    cvss_score Float32,
    description String,
    affected_products Array(String),
    ai_triage_notes String
)
ENGINE = ReplacingMergeTree
PARTITION BY toYYYYMM(published_date)
ORDER BY cve_id;
