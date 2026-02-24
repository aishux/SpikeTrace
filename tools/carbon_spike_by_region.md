# Tool Documentation: `carbon_spike_by_region`

## Overview

**Tool ID:** `carbon_spike_by_region`

**Description:** Finds carbon emissions and CPU metrics aggregated by region and service over time. Use when investigating why emissions spiked, comparing regions, or identifying high-CO2 services.

## Configuration

* **Type:** ES|QL

### ES|QL Query

```sql
FROM spiketrace-carbon-metrics-*
| WHERE @timestamp > NOW() - TO_TIMEDURATION(?time_window)
| WHERE region == ?region
| STATS 
    avg_cpu = AVG(cpu_pct), 
    avg_co2 = AVG(estimated_co2_grams),
    avg_rps = AVG(requests_per_min)
  BY service, region, bucket_ts = BUCKET(@timestamp, 10 minutes)
| SORT bucket_ts DESC
| LIMIT 100

```

### Parameters

| Name | Description | Type | Optional |
| --- | --- | --- | --- |
| `region` | Filter by region, e.g. "us-central1" | keyword | No |
| `time_window` | Time span string, e.g. "24 hours" or "6 hours" | keyword | No |

## Metadata

* **Labels:** 
* `carbon`
* `observability`
* `retrieval`
* `spike_tracer_project`