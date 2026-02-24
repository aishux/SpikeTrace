# Tool Documentation: `excess_runtime_waste`

## Overview

**Tool ID:** `excess_runtime_waste`

**Description:** Estimates excess compute waste from retries and errors. Quantifies carbon impact of inefficient retry behavior.

## Configuration

* **Type:** ES|QL

### ES|QL Query

```sql
FROM spiketrace-logs-*
| WHERE @timestamp > NOW() - 6 hours
| WHERE service == ?service AND region == ?region
| WHERE retry == true OR level == 'ERROR'
| STATS
    retry_count = COUNT(*),
    excess_latency_ms = SUM(latency_ms)
  BY service, region, error_type

```

### Parameters

| Name | Description | Type | Optional |
| --- | --- | --- | --- |
| `service` | Service name | keyword | No |
| `region` | Region | keyword | No |

## Metadata

* **Labels:** `carbon`, `retrieval`, `spike_tracer_project`