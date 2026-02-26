import os
import random
import sys
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from elasticsearch import Elasticsearch, helpers

# Allow importing carbon_utils when running from repo root (python scripts/seed_demo_data.py)
_scripts_dir = os.path.dirname(os.path.abspath(__file__))
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)
from carbon_utils import estimate_co2_grams_formula


def get_es_client() -> Elasticsearch:
    load_dotenv()
    api_key = os.getenv("ELASTICSEARCH_API_KEY")
    cloud_id = os.getenv("ELASTICSEARCH_CLOUD_ID")
    endpoint = os.getenv("ELASTICSEARCH_ENDPOINT")

    if not api_key:
        raise RuntimeError("ELASTICSEARCH_API_KEY is required")

    if cloud_id:
        return Elasticsearch(cloud_id=cloud_id, api_key=api_key)
    if endpoint:
        return Elasticsearch(endpoint, api_key=api_key)

    raise RuntimeError("Either ELASTICSEARCH_CLOUD_ID or ELASTICSEARCH_ENDPOINT must be set")


def index_name(prefix: str, base: str) -> str:
    idx_prefix = os.getenv("ELASTICSEARCH_INDEX_PREFIX", "spiketrace")
    return f"{idx_prefix}-{base}"


def create_indices(es: Elasticsearch) -> None:
    carbon_metrics_index = index_name("spiketrace", "carbon-metrics-0001")
    logs_index = index_name("spiketrace", "logs-0001")
    deployments_index = index_name("spiketrace", "deployments-0001")
    incidents_index = index_name("spiketrace", "incidents")

    if not es.indices.exists(index=carbon_metrics_index):
        es.indices.create(
            index=carbon_metrics_index,
            mappings={
                "properties": {
                    "@timestamp": {"type": "date"},
                    "service": {"type": "keyword"},
                    "region": {"type": "keyword"},
                    "cloud.provider": {"type": "keyword"},
                    "cpu_pct": {"type": "float"},
                    "memory_pct": {"type": "float"},
                    "requests_per_min": {"type": "float"},
                    "estimated_co2_grams": {"type": "float"},
                    "emissions_kg_co2e": {"type": "float"},
                    "deployment_id": {"type": "keyword"},
                }
            },
        )

    if not es.indices.exists(index=logs_index):
        es.indices.create(
            index=logs_index,
            mappings={
                "properties": {
                    "@timestamp": {"type": "date"},
                    "service": {"type": "keyword"},
                    "region": {"type": "keyword"},
                    "level": {"type": "keyword"},
                    "message": {"type": "text"},
                    "error_type": {"type": "keyword"},
                    "deployment_id": {"type": "keyword"},
                    "retry": {"type": "boolean"},
                    "latency_ms": {"type": "float"},
                }
            },
        )

    if not es.indices.exists(index=deployments_index):
        es.indices.create(
            index=deployments_index,
            mappings={
                "properties": {
                    "@timestamp": {"type": "date"},
                    "service": {"type": "keyword"},
                    "region": {"type": "keyword"},
                    "deployment_id": {"type": "keyword"},
                    "version": {"type": "keyword"},
                    "status": {"type": "keyword"},
                }
            },
        )

    if not es.indices.exists(index=incidents_index):
        es.indices.create(
            index=incidents_index,
            mappings={
                "properties": {
                    "@timestamp": {"type": "date"},
                    "title": {"type": "text"},
                    "summary": {"type": "text"},
                    "service": {"type": "keyword"},
                    "region": {"type": "keyword"},
                    "tags": {"type": "keyword"},
                    "severity": {"type": "keyword"},
                    "status": {"type": "keyword"},
                    "duration_minutes": {"type": "float"},
                    "wasted_co2_grams": {"type": "float"},
                    "wasted_emissions_kg_co2e": {"type": "float"},
                    "orders_affected": {"type": "integer"},
                    "revenue_lost_usd": {"type": "float"},
                    "embedding": {
                        "type": "dense_vector",
                        "dims": 384,
                        "index": True,
                        "similarity": "cosine",
                    },
                }
            },
        )


def generate_carbon_spike_data(base_time: datetime):
    """
    Generate carbon/metrics data for the demo.
    Carbon (estimated_co2_grams) is computed from CPU% and region using
    real grid intensity (see carbon_utils). Spike window still has higher CPU
    so CO2 is higher; no synthetic random CO2.
    """
    services = ["checkout", "payments", "inventory"]
    regions = ["us-central1", "europe-west1"]

    # Define explicit spike scenarios per service/region so the agent can answer
    # questions about non-checkout services too.
    # Offsets are in minutes relative to base_time.
    spike_scenarios = {
        ("checkout", "us-central1"): {"start": 0, "duration": 60},
        # Inventory spike in europe-west1 before the checkout spike window
        ("inventory", "europe-west1"): {"start": -60, "duration": 45},
        # Payments spike in europe-west1 overlapping slightly with checkout
        ("payments", "europe-west1"): {"start": 30, "duration": 45},
    }

    bad_deployments = {
        ("checkout", "us-central1"): "deploy-checkout-bad",
        ("inventory", "europe-west1"): "deploy-inventory-bad",
        ("payments", "europe-west1"): "deploy-payments-bad",
    }
    good_deployments = {
        ("checkout", "us-central1"): "deploy-checkout-good",
        ("inventory", "europe-west1"): "deploy-inventory-good",
        ("payments", "europe-west1"): "deploy-payments-good",
    }

    # 2 hours before earliest spike, 1 hour after (5-min windows)
    docs = []
    for minutes_offset in range(-120, 120, 5):
        ts = base_time + timedelta(minutes=minutes_offset)
        for service in services:
            for region in regions:
                scenario = spike_scenarios.get((service, region))
                is_spike_window = False
                if scenario is not None:
                    start = scenario["start"]
                    duration = scenario["duration"]
                    is_spike_window = start <= minutes_offset < start + duration

                cpu = random.uniform(30, 60)
                mem = random.uniform(40, 70)
                rps = random.uniform(200, 400)

                if is_spike_window:
                    # Slightly different spike shapes per service
                    if service == "checkout":
                        cpu = random.uniform(80, 95)
                        mem = random.uniform(70, 90)
                        rps = random.uniform(400, 700)
                    elif service == "inventory":
                        cpu = random.uniform(70, 88)
                        mem = random.uniform(65, 85)
                        rps = random.uniform(300, 550)
                    else:  # payments
                        cpu = random.uniform(75, 92)
                        mem = random.uniform(68, 88)
                        rps = random.uniform(350, 650)

                co2 = estimate_co2_grams_formula(cpu, region, window_minutes=5.0)
                emissions_kg = co2 / 1000.0

                if is_spike_window:
                    deployment_id = bad_deployments.get((service, region), "deploy-checkout-bad")
                else:
                    deployment_id = good_deployments.get((service, region), "deploy-checkout-good")

                docs.append(
                    {
                        "_index": index_name("spiketrace", "carbon-metrics-0001"),
                        "_source": {
                            "@timestamp": ts.isoformat(),
                            "service": service,
                            "region": region,
                            "cloud.provider": "gcp",
                            "cpu_pct": round(cpu, 2),
                            "memory_pct": round(mem, 2),
                            "requests_per_min": round(rps, 2),
                            "estimated_co2_grams": co2,
                            "emissions_kg_co2e": emissions_kg,
                            "deployment_id": deployment_id,
                        },
                    }
                )
    return docs


def generate_logs_and_deployments(base_time: datetime):
    logs = []
    deployments = []

    # Deployment just before checkout spike
    deployments.append(
        {
            "_index": index_name("spiketrace", "deployments-0001"),
            "_source": {
                "@timestamp": (base_time - timedelta(minutes=5)).isoformat(),
                "service": "checkout",
                "region": "us-central1",
                "deployment_id": "deploy-checkout-bad",
                "version": "v2.3.0",
                "status": "succeeded",
            },
        }
    )

    # Good deployment earlier for contrast
    deployments.append(
        {
            "_index": index_name("spiketrace", "deployments-0001"),
            "_source": {
                "@timestamp": (base_time - timedelta(hours=4)).isoformat(),
                "service": "checkout",
                "region": "us-central1",
                "deployment_id": "deploy-checkout-good",
                "version": "v2.2.5",
                "status": "succeeded",
            },
        }
    )

    # Problematic deployments for inventory and payments so the agent can
    # correlate non-checkout spikes with concrete deploys.
    deployments.append(
        {
            "_index": index_name("spiketrace", "deployments-0001"),
            "_source": {
                "@timestamp": (base_time - timedelta(minutes=70)).isoformat(),
                "service": "inventory",
                "region": "europe-west1",
                "deployment_id": "deploy-inventory-bad",
                "version": "v1.4.0",
                "status": "succeeded",
            },
        }
    )
    deployments.append(
        {
            "_index": index_name("spiketrace", "deployments-0001"),
            "_source": {
                "@timestamp": (base_time - timedelta(hours=3)).isoformat(),
                "service": "inventory",
                "region": "europe-west1",
                "deployment_id": "deploy-inventory-good",
                "version": "v1.3.5",
                "status": "succeeded",
            },
        }
    )
    deployments.append(
        {
            "_index": index_name("spiketrace", "deployments-0001"),
            "_source": {
                "@timestamp": (base_time + timedelta(minutes=25)).isoformat(),
                "service": "payments",
                "region": "europe-west1",
                "deployment_id": "deploy-payments-bad",
                "version": "v3.1.0",
                "status": "succeeded",
            },
        }
    )
    deployments.append(
        {
            "_index": index_name("spiketrace", "deployments-0001"),
            "_source": {
                "@timestamp": (base_time - timedelta(hours=5)).isoformat(),
                "service": "payments",
                "region": "europe-west1",
                "deployment_id": "deploy-payments-good",
                "version": "v3.0.4",
                "status": "succeeded",
            },
        }
    )

    # Additional historical deployments for richer failure timelines
    services = ["checkout", "payments", "inventory"]
    regions = ["us-central1", "europe-west1"]
    for days_ago in range(1, 15):
        for service in services:
            for region in regions:
                ts = base_time - timedelta(
                    days=days_ago,
                    hours=random.randint(0, 23),
                    minutes=random.randint(0, 59),
                )
                status = random.choices(
                    ["succeeded", "failed", "rolled_back"],
                    weights=[6, 2, 1],
                )[0]
                deployment_id = f"deploy-{service}-{region.replace('-', '')}-{days_ago:02d}"
                version = f"v{2 + days_ago // 10}.{random.randint(0,9)}.{random.randint(0,9)}"
                deployments.append(
                    {
                        "_index": index_name("spiketrace", "deployments-0001"),
                        "_source": {
                            "@timestamp": ts.isoformat(),
                            "service": service,
                            "region": region,
                            "deployment_id": deployment_id,
                            "version": version,
                            "status": status,
                        },
                    }
                )

    # Logs around checkout spike window
    for minutes_offset in range(-60, 120, 2):
        ts = base_time + timedelta(minutes=minutes_offset)
        is_spike_window = 0 <= minutes_offset < 60

        if is_spike_window:
            # Retry storm during spike
            for _ in range(5):
                logs.append(
                    {
                        "_index": index_name("spiketrace", "logs-0001"),
                        "_source": {
                            "@timestamp": ts.isoformat(),
                            "service": "checkout",
                            "region": "us-central1",
                            "level": "ERROR",
                            "message": "Checkout request failed, retrying",
                            "error_type": "UpstreamTimeout",
                            "deployment_id": "deploy-checkout-bad",
                            "retry": True,
                            "latency_ms": random.uniform(800, 1500),
                        },
                    }
                )
        else:
            # Normal traffic
            logs.append(
                {
                    "_index": index_name("spiketrace", "logs-0001"),
                    "_source": {
                        "@timestamp": ts.isoformat(),
                        "service": "checkout",
                        "region": "us-central1",
                        "level": "INFO",
                        "message": "Checkout request succeeded",
                        "error_type": None,
                        "deployment_id": "deploy-checkout-good",
                        "retry": False,
                        "latency_ms": random.uniform(120, 250),
                    },
                }
            )

    # Additional logs for inventory and payments spikes so that the error_rate
    # tools see real anomalies for these services as well.
    spike_log_configs = [
        {
            "service": "inventory",
            "region": "europe-west1",
            "start": -60,
            "duration": 45,
            "error_type": "DbLockTimeout",
            "error_message": "Inventory update failed due to DB lock timeout, retrying",
            "ok_message": "Inventory update succeeded",
            "bad_deployment": "deploy-inventory-bad",
            "good_deployment": "deploy-inventory-good",
        },
        {
            "service": "payments",
            "region": "europe-west1",
            "start": 30,
            "duration": 45,
            "error_type": "ThirdPartyGatewayError",
            "error_message": "Payment authorization failed due to gateway error, retrying",
            "ok_message": "Payment authorization succeeded",
            "bad_deployment": "deploy-payments-bad",
            "good_deployment": "deploy-payments-good",
        },
    ]

    for cfg in spike_log_configs:
        for minutes_offset in range(-120, 120, 5):
            ts = base_time + timedelta(minutes=minutes_offset)
            in_spike = cfg["start"] <= minutes_offset < cfg["start"] + cfg["duration"]
            if in_spike:
                for _ in range(3):
                    logs.append(
                        {
                            "_index": index_name("spiketrace", "logs-0001"),
                            "_source": {
                                "@timestamp": ts.isoformat(),
                                "service": cfg["service"],
                                "region": cfg["region"],
                                "level": "ERROR",
                                "message": cfg["error_message"],
                                "error_type": cfg["error_type"],
                                "deployment_id": cfg["bad_deployment"],
                                "retry": True,
                                "latency_ms": random.uniform(700, 1400),
                            },
                        }
                    )
            else:
                logs.append(
                    {
                        "_index": index_name("spiketrace", "logs-0001"),
                        "_source": {
                            "@timestamp": ts.isoformat(),
                            "service": cfg["service"],
                            "region": cfg["region"],
                            "level": "INFO",
                            "message": cfg["ok_message"],
                            "error_type": None,
                            "deployment_id": cfg["good_deployment"],
                            "retry": False,
                            "latency_ms": random.uniform(100, 260),
                        },
                    }
                )

    return logs, deployments


def generate_incidents():
    base_index = index_name("spiketrace", "incidents")
    now = datetime.now(timezone.utc)

    # For now we use simple random vectors as placeholders; in a real system these
    # would be generated by an embedding model.
    def random_embedding(dim: int = 384):
        return [random.uniform(-1, 1) for _ in range(dim)]

    docs = []

    # Curated anchor incidents that tie retries/failures to carbon spikes
    curated_incidents = [
        {
            "relative_time": timedelta(days=30),
            "title": "Retry-induced carbon spike in us-central1",
            "summary": "A misconfigured checkout deployment caused retry storms, driving up user-facing checkout failures, latency, and CO2 emissions by ~30% for 2 hours.",
            "service": "checkout",
            "region": "us-central1",
            "tags": ["carbon", "retries", "checkout"],
            "severity": "high",
            "status": "resolved",
            "duration_minutes": 120.0,
            "orders_affected": 850,
            "revenue_lost_usd": 850 * 85.0,
        },
        {
            "relative_time": timedelta(days=60),
            "title": "Excess compute waste from error loop in payments",
            "summary": "Payments service entered an error loop due to a bad feature flag, causing intermittent card declines and retries for users and wasting CPU.",
            "service": "payments",
            "region": "europe-west1",
            "tags": ["waste", "errors", "payments"],
            "severity": "medium",
            "status": "resolved",
            "duration_minutes": 90.0,
            "orders_affected": 430,
            "revenue_lost_usd": 430 * 95.0,
        },
        {
            "relative_time": timedelta(days=10),
            "title": "Inventory replication lag causing carbon-heavy retries",
            "summary": "Inventory service in europe-west1 experienced replication lag, causing inconsistent stock levels for users, repeated retry storms, and elevated CO2 emissions.",
            "service": "inventory",
            "region": "europe-west1",
            "tags": ["carbon", "retries", "inventory"],
            "severity": "high",
            "status": "resolved",
            "duration_minutes": 180.0,
            "orders_affected": 620,
            "revenue_lost_usd": 620 * 60.0,
        },
        {
            "relative_time": timedelta(days=5),
            "title": "Carbon spike from overprovisioned inventory capacity in us-central1",
            "summary": "Overprovisioned inventory pods in us-central1 ran at high idle CPU for several hours, wasting compute and increasing emissions even though user-facing behavior remained stable.",
            "service": "inventory",
            "region": "us-central1",
            "tags": ["carbon", "waste", "overprovisioning", "inventory"],
            "severity": "medium",
            "status": "resolved",
            "duration_minutes": 240.0,
            "orders_affected": 0,
            "revenue_lost_usd": 0.0,
        },
    ]

    for incident in curated_incidents:
        duration = incident["duration_minutes"]
        wasted_co2 = estimate_co2_grams_formula(
            cpu_pct=60.0,
            region=incident["region"],
            window_minutes=duration,
        )
        wasted_kg = wasted_co2 / 1000.0
        docs.append(
            {
                "_index": base_index,
                "_source": {
                    "@timestamp": (now - incident["relative_time"]).isoformat(),
                    "title": incident["title"],
                    "summary": incident["summary"],
                    "service": incident["service"],
                    "region": incident["region"],
                    "tags": incident["tags"],
                    "severity": incident["severity"],
                    "status": incident["status"],
                    "duration_minutes": duration,
                    "orders_affected": incident.get("orders_affected", 0),
                    "revenue_lost_usd": incident.get("revenue_lost_usd", 0.0),
                    "wasted_co2_grams": wasted_co2,
                    "wasted_emissions_kg_co2e": wasted_kg,
                    "embedding": random_embedding(),
                },
            }
        )

    # Additional synthetic incidents focused on failures vs carbon waste (roughly 50/50)
    services = ["checkout", "payments", "inventory"]
    regions = ["us-central1", "europe-west1"]
    severities = ["low", "medium", "high", "critical"]
    statuses = ["open", "mitigated", "resolved"]

    for i in range(40):
        service = random.choice(services)
        region = random.choice(regions)
        severity = random.choices(severities, weights=[1, 2, 3, 1])[0]
        status = random.choice(statuses)
        # Spread incidents over the last ~90 days
        ts = now - timedelta(
            days=random.randint(1, 90),
            hours=random.randint(0, 23),
            minutes=random.randint(0, 59),
        )
        duration = random.uniform(15.0, 180.0)

        # Approximate wasted CO2 from excess CPU during the incident window
        extra_cpu_pct = random.uniform(10.0, 60.0)
        wasted_co2 = estimate_co2_grams_formula(
            cpu_pct=extra_cpu_pct,
            region=region,
            window_minutes=duration,
        )
        wasted_kg = wasted_co2 / 1000.0

        # Rough e-commerce business impact model:
        # assume base throughput proportional to duration, and scale by severity.
        severity_multiplier = {
            "low": 0.3,
            "medium": 0.6,
            "high": 1.0,
            "critical": 1.5,
        }.get(severity, 0.5)
        # Base: ~5 affected orders per minute at multiplier 1.0
        orders_affected = int((duration * 5.0 / 60.0) * severity_multiplier * random.uniform(0.7, 1.3))
        avg_order_value_usd = {
            "checkout": 85.0,
            "payments": 95.0,
            "inventory": 60.0,
        }.get(service, 80.0)
        revenue_lost = float(orders_affected) * avg_order_value_usd

        if i % 2 == 0:
            # Failure/incident-first narrative
            title = f"{service.capitalize()} error spike causing retries in {region}"
            summary = (
                f"{service.capitalize()} experienced elevated error rates and retry storms in {region}, "
                f"driving up CPU and wasting capacity for approximately {int(duration)} minutes."
            )
            tags = ["incident", "errors", "retries", "carbon"]
        else:
            # Carbon-waste-first narrative
            title = f"Carbon waste from idle {service} capacity in {region}"
            summary = (
                f"Overprovisioned {service} pods in {region} ran far above needed capacity for "
                f"about {int(duration)} minutes, leading to avoidable CO2 emissions."
            )
            tags = ["carbon", "waste", "overprovisioning", service]

        docs.append(
            {
                "_index": base_index,
                "_source": {
                    "@timestamp": ts.isoformat(),
                    "title": title,
                    "summary": summary,
                    "service": service,
                    "region": region,
                    "tags": tags,
                    "severity": severity,
                    "status": status,
                    "duration_minutes": duration,
                    "orders_affected": orders_affected,
                    "revenue_lost_usd": revenue_lost,
                    "wasted_co2_grams": wasted_co2,
                    "wasted_emissions_kg_co2e": wasted_kg,
                    "embedding": random_embedding(),
                },
            }
        )

    return docs


def main():
    es = get_es_client()
    create_indices(es)

    # Center the synthetic spike close to \"now\" so it shows up in
    # default Kibana time ranges like \"Last 15 minutes\" or \"Last 1 hour\".
    base_time = datetime.now(timezone.utc) - timedelta(hours=1)

    carbon_docs = generate_carbon_spike_data(base_time)
    log_docs, deployment_docs = generate_logs_and_deployments(base_time)
    incident_docs = generate_incidents()

    all_docs = carbon_docs + log_docs + deployment_docs + incident_docs

    print(f"Indexing {len(all_docs)} documents...")
    helpers.bulk(es, all_docs)
    print("Done. Demo data loaded.")


if __name__ == "__main__":
    main()

