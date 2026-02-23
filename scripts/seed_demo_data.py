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
                    "cpu_pct": {"type": "float"},
                    "memory_pct": {"type": "float"},
                    "requests_per_min": {"type": "float"},
                    "estimated_co2_grams": {"type": "float"},
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

    # 2 hours before spike, 1 hour spike, 1 hour after (5-min windows)
    docs = []
    for minutes_offset in range(-120, 120, 5):
        ts = base_time + timedelta(minutes=minutes_offset)
        for service in services:
            for region in regions:
                is_spike_window = region == "us-central1" and service == "checkout" and 0 <= minutes_offset < 60

                cpu = random.uniform(30, 60)
                mem = random.uniform(40, 70)
                rps = random.uniform(200, 400)

                if is_spike_window:
                    cpu = random.uniform(80, 95)
                    mem = random.uniform(70, 90)
                    rps = random.uniform(400, 700)

                co2 = estimate_co2_grams_formula(cpu, region, window_minutes=5.0)

                docs.append(
                    {
                        "_index": index_name("spiketrace", "carbon-metrics-0001"),
                        "_source": {
                            "@timestamp": ts.isoformat(),
                            "service": service,
                            "region": region,
                            "cpu_pct": round(cpu, 2),
                            "memory_pct": round(mem, 2),
                            "requests_per_min": round(rps, 2),
                            "estimated_co2_grams": co2,
                            "deployment_id": "deploy-checkout-bad"
                            if is_spike_window
                            else "deploy-checkout-good",
                        },
                    }
                )
    return docs


def generate_logs_and_deployments(base_time: datetime):
    logs = []
    deployments = []

    # Deployment just before spike
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

    # Logs around spike window
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

    return logs, deployments


def generate_incidents():
    base_index = index_name("spiketrace", "incidents")

    # For now we use simple random vectors as placeholders; in a real system these
    # would be generated by an embedding model.
    def random_embedding(dim: int = 384):
        return [random.uniform(-1, 1) for _ in range(dim)]

    docs = [
        {
            "_index": base_index,
            "_source": {
                "@timestamp": (datetime.now(timezone.utc) - timedelta(days=30)).isoformat(),
                "title": "Retry-induced carbon spike in us-central1",
                "summary": "A misconfigured checkout deployment caused retry storms, driving CPU and CO2 emissions up by ~30% for 2 hours.",
                "service": "checkout",
                "region": "us-central1",
                "tags": ["carbon", "retries", "checkout"],
                "embedding": random_embedding(),
            },
        },
        {
            "_index": base_index,
            "_source": {
                "@timestamp": (datetime.now(timezone.utc) - timedelta(days=60)).isoformat(),
                "title": "Excess compute waste from error loop in payments",
                "summary": "Payments service entered an error loop due to a bad feature flag, wasting CPU without user-visible impact.",
                "service": "payments",
                "region": "europe-west1",
                "tags": ["waste", "errors", "payments"],
                "embedding": random_embedding(),
            },
        },
    ]
    return docs


def main():
    es = get_es_client()
    create_indices(es)

    base_time = datetime.now(timezone.utc) - timedelta(hours=3)

    carbon_docs = generate_carbon_spike_data(base_time)
    log_docs, deployment_docs = generate_logs_and_deployments(base_time)
    incident_docs = generate_incidents()

    all_docs = carbon_docs + log_docs + deployment_docs + incident_docs

    print(f"Indexing {len(all_docs)} documents...")
    helpers.bulk(es, all_docs)
    print("Done. Demo data loaded.")


if __name__ == "__main__":
    main()

