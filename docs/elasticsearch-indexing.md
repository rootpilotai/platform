# Elasticsearch Indexing Strategy

## Index Naming Convention

Daily rolling indices with a short prefix:

```
rp-tl-{yyyy.MM.dd}
```

- `rp` &mdash; RootPilot
- `tl` &mdash; telemetry/logs
- `2026.06.13` &mdash; UTC date of the data

**Example indices:**

| Index | Contents |
|---|---|
| `rp-tl-2026.06.13` | All telemetry ingested on June 13, 2026 |
| `rp-tl-2026.06.14` | All telemetry ingested on June 14, 2026 |

An index template `rp-tl-template` matches `rp-tl-*` and applies consistent settings and mappings automatically.

---

## Index Template: `rp-tl-template`

### Settings

| Setting | Value | Notes |
|---|---|---|
| `number_of_shards` | 1 | Single shard per daily index (adjust as volume grows) |
| `number_of_replicas` | 0 | Single-node dev default; set >=1 for HA in production |
| `index.lifecycle.name` | `rp-tl-ilm-policy` | ILM policy for rollover and retention |
| `index.lifecycle.rollover_alias` | `rp-tl` | Rollover alias for the index pattern |

### Mappings

```json
{
  "dynamic": "strict",
  "properties": {
    "@timestamp":     { "type": "date" },
    "event_id":       { "type": "keyword" },
    "service":        { "type": "keyword" },
    "level":          { "type": "keyword" },
    "message":        { "type": "text", "analyzer": "english" },
    "trace_id":       { "type": "keyword" },
    "span_id":        { "type": "keyword" },
    "correlation_id": { "type": "keyword" },
    "metadata":       { "type": "flattened" }
  }
}
```

**Field notes:**

| Field | Type | Purpose |
|---|---|---|
| `@timestamp` | `date` | Event timestamp (UTC ISO-8601). Used as the primary sort and time-filter field. |
| `event_id` | `keyword` | Unique event identifier. Supports exact-match lookups. |
| `service` | `keyword` | Logical service name (e.g. `ingestion-service`, `gateway-service`). Used for filtering and aggregation. |
| `level` | `keyword` | Log severity (`INFO`, `WARN`, `ERROR`, `DEBUG`). Enables level-based filtering. |
| `message` | `text` (english) | Human-readable log message with English-language stemming. Supports full-text search. |
| `trace_id` | `keyword` | OpenTelemetry trace ID. Enables trace-centric investigation queries. |
| `span_id` | `keyword` | OpenTelemetry span ID. Supports fine-grained span-level lookups. |
| `correlation_id` | `keyword` | Correlation group ID assigned by the correlation-service. Enables grouped incident analysis. |
| `metadata` | `flattened` | Arbitrary key-value context (e.g. `retry_count`, `endpoint`). The `flattened` type indexes each sub-field as a keyword without needing an explicit mapping. |

The mapping uses `"dynamic": "strict"` so unexpected fields cause indexing to reject the document rather than silently create unwanted mappings.

---

## ILM Policy: `rp-tl-ilm-policy`

| Phase | Min Age | Actions |
|---|---|---|
| **Hot** | `0ms` | `rollover` after 1 day or 50 GB primary shard size |
| **Warm** | `7d` | `forcemerge` to 1 segment, lower priority |
| **Cold** | `30d` | Lower priority, searchable but not writable |
| **Delete** | `90d` | Hard-delete expired indices |

---

## Query Patterns

### Trace-ID Lookup

Fetch all log entries belonging to a specific trace:

```json
POST rp-tl-*/_search
{
  "query": {
    "term": { "trace_id": "abc123def456" }
  },
  "sort": { "@timestamp": "asc" }
}
```

### Time-Range + Service Filter

```json
POST rp-tl-*/_search
{
  "query": {
    "bool": {
      "must": [
        { "term":  { "service": "ingestion-service" } },
        { "range": { "@timestamp": { "gte": "2026-06-13T00:00:00Z", "lte": "2026-06-13T23:59:59Z" } } }
      ]
    }
  },
  "sort": { "@timestamp": "desc" }
}
```

### Error Aggregation (Top Error Services)

```json
POST rp-tl-*/_search
{
  "size": 0,
  "query": {
    "term": { "level": "ERROR" }
  },
  "aggs": {
    "by_service": {
      "terms": { "field": "service", "size": 10 }
    }
  }
}
```

### Full-Text Search Across Messages

```json
POST rp-tl-*/_search
{
  "query": {
    "query_string": {
      "query": "connection AND refused"
    }
  },
  "sort": { "@timestamp": "desc" }
}
```

### Pagination with Offset

```json
POST rp-tl-*/_search
{
  "from": 100,
  "size": 50,
  "query": { "match_all": {} },
  "sort": { "@timestamp": "desc" }
}
```

---

## Adapter API

The `ElasticsearchLogStore` implements the provider-agnostic `LogStore` interface:

| Method | Description |
|---|---|
| `write(entry)` | Index a single `LogEntry` into the appropriate daily index |
| `write_batch(entries)` | Bulk-index a list of entries using Elasticsearch `_bulk` API |
| `query(filter)` | Async-iterate matching `LogEntry` objects from `rp-tl-*` indices |
| `count(filter)` | Return the count of matching documents |
| `health()` | Ping the cluster; returns `True` if reachable |

The `start()` method bootstraps the ILM policy and index template on first connection.

---

## Retention Strategy

| Horizon | Storage Tier | Purpose |
|---|---|---|
| 0 &ndash; 7 days | Hot (SSD) | Active investigation, real-time queries |
| 8 &ndash; 30 days | Warm (HDD) | Recent incident review, post-mortem analysis |
| 31 &ndash; 90 days | Cold (HDD) | Compliance, audit, historical trend analysis |
| > 90 days | Deleted | Retention limit |

This is managed entirely by the ILM policy. No external scripts are needed.

---

## Future Considerations

- **Replicas**: Set `number_of_replicas: 1` (or higher) when running a multi-node cluster in production.
- **Shard count**: Adjust `number_of_shards` upward when daily volume exceeds 40-50 GB per shard.
- **Searchable snapshots**: For longer retention (>90 days), replace the delete phase with a searchable snapshot policy.
- **Custom analyzers**: Add language-specific analyzers (e.g. `kuromoji` for Japanese logs) as needed.
- **Rollup / downsampling**: For long-term metrics, use Elasticsearch rollup jobs to reduce storage cost.
