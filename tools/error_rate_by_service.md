# Tool Documentation: `error_rate_by_service`

## Overview

**Tool ID:** `error_rate_by_service`

**Description:** Counts errors and retries by service and region. Use to confirm retry storms or error loops during a carbon spike.

## Configuration

* **Type:** ES|QL

### ES|QL Query

```sql
FROM spiketrace-logs-*
| WHERE @timestamp > NOW() - TO_TIMEDURATION(?time_window)
| WHERE service == ?service AND region == ?region
| WHERE level == 'ERROR' OR retry == true
| STATS error_count = COUNT(*), avg_latency = AVG(latency_ms)
  BY service, region, error_type, bucket_ts = BUCKET(@timestamp, 5 minutes)
| SORT bucket_ts DESC
| LIMIT 50

```

### Parameters

| Name | Description | Type | Optional |
| --- | --- | --- | --- |
| `service` | Service name | keyword | No |
| `region` | Region | keyword | No |
| `time_window` | Time span string, e.g. "6 hours" or "24 hours" | keyword | No |

## Metadata

* **Labels:** `observability`, `logs`, `retrieval`, `spike_tracer_project`