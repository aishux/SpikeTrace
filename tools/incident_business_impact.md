# Tool Documentation: `incident_business_impact`

## Overview

**Tool ID:** `incident_business_impact`

**Description:** Summarizes incidents from the `spiketrace-incidents` index, including user, carbon, and business impact. Use when the user asks about incidents, affected orders, revenue loss, or wants a high-level view of how failures and carbon waste translate into business impact.

## Configuration

* **Type:** ES|QL

### ES|QL Query

```sql
FROM spiketrace-incidents
| WHERE @timestamp > NOW() - TO_TIMEDURATION(?time_window)
  AND service == ?service
  AND region == ?region
| SORT @timestamp DESC
| KEEP
    @timestamp,
    title,
    service,
    region,
    severity,
    status,
    duration_minutes,
    orders_affected,
    revenue_lost_usd,
    wasted_emissions_kg_co2e,
    wasted_co2_grams,
    tags
| LIMIT 50
```

### Parameters

| Name | Description | Type | Optional |
| --- | --- | --- | --- |
| `service` | Service name, e.g. "checkout", "payments", "inventory" | keyword | No |
| `region` | Region, e.g. "us-central1" or "europe-west1" | keyword | No |
| `time_window` | Time span string, e.g. "24 hours", "7 days", or "30 days" | keyword | No |

## Metadata

* **Labels:**
* `observability`
* `carbon`
* `business`
* `retrieval`
* `spike_tracer_project`

