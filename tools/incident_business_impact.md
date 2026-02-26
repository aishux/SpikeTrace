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
| STATS
    incident_count = COUNT(*),
    total_orders_affected = SUM(orders_affected),
    total_revenue_lost_usd = SUM(revenue_lost_usd),
    total_wasted_emissions_kg_co2e = SUM(wasted_emissions_kg_co2e)
  BY service, region
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

