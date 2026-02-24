# Tool Documentation: `deployment_timeline`

## Overview

**Tool ID:** `deployment_timeline`

**Description:** Returns deployment events for a service and region. Use to correlate carbon spikes with recent deployments.

## Configuration

* **Type:** ES|QL

### ES|QL Query

```sql
FROM spiketrace-deployments-*
| WHERE @timestamp > NOW() - TO_TIMEDURATION(?time_window)
| WHERE service == ?service AND region == ?region
| SORT @timestamp DESC
| KEEP @timestamp, deployment_id, version, status, service, region
| LIMIT 20

```

### Parameters

| Name | Description | Type | Optional |
| --- | --- | --- | --- |
| `time_window` | Time Window | keyword | No |
| `service` | Service name | keyword | No |
| `region` | Time span string, e.g. "24 hours" or "6 hours" | keyword | No |

## Metadata

* **Labels:**
* `observability`
* `retrieval`
* `spike_tracer_project`
