#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = [
#   "requests",
# ]
# ///
"""Large-message load generator for search index stress testing.

Generates conversations with realistic, large input_messages arrays that
simulate pre-compaction conversation histories — each turn carries the full
growing history of messages, like a real agent that hasn't compacted yet.

Messages contain diverse, unique text drawn from multiple domains so the
search index has meaningful content to match against.

Usage:
    devall uv run examples/otel_genai/large_message_load_gen.py
    devall uv run examples/otel_genai/large_message_load_gen.py --conversations 100 --turns-per-conv 20
    devall uv run examples/otel_genai/large_message_load_gen.py --conversations 1000 --turns-per-conv 50 --concurrency 10
"""

import argparse
import os
import random
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

# ---------------------------------------------------------------------------
# Diverse text corpus — each domain produces unique, searchable content
# ---------------------------------------------------------------------------

DOMAINS = {
    "software_engineering": {
        "user_templates": [
            "Can you help me debug the {component} in our {language} codebase? I'm seeing {error_type} errors when {action}. The stack trace shows the issue is in {file_path} around line {line_num}. We're running version {version} of the {framework} framework.",
            "I need to refactor the {component} module. Currently it has {num} lines and handles both {responsibility_a} and {responsibility_b}. What's the best way to split this while maintaining backward compatibility with the {api_name} API?",
            "Our CI pipeline is failing on the {test_type} tests. The {test_name} test passes locally but fails in {ci_env}. I suspect it's related to the {dependency} version mismatch. Here's the error output:\n\n```\n{error_output}\n```",
            "I'm implementing a new {feature} feature that requires changes to the {layer} layer. The current architecture uses {pattern} pattern but I think we should migrate to {new_pattern} for better {quality_attr}. What are the tradeoffs?",
            "Can you review this database migration? We're adding a {column_type} column to the {table_name} table with {num_rows} million rows. I'm worried about lock contention during the ALTER TABLE on {db_engine}.",
        ],
        "assistant_templates": [
            "Looking at the {component} code, the {error_type} is caused by a race condition in the {method} method. When multiple threads call {action} simultaneously, the shared {resource} isn't properly synchronized.\n\nHere's the fix:\n\n```{language}\n{code_block}\n```\n\nThe key changes are:\n1. Added a mutex lock around the {resource} access\n2. Changed the {data_structure} from a plain {old_type} to a thread-safe {new_type}\n3. Added retry logic with exponential backoff for the {external_call}\n\nYou should also add a test that exercises the concurrent path — I'd suggest using {test_framework}'s {test_util} for this.",
            "The refactoring approach I'd recommend is to extract {responsibility_a} into a dedicated {new_class_a} class and {responsibility_b} into {new_class_b}. Here's the migration plan:\n\n**Phase 1: Extract interfaces**\n- Define {interface_a} with methods: {methods_a}\n- Define {interface_b} with methods: {methods_b}\n\n**Phase 2: Implement new classes**\n- {new_class_a} implements {interface_a}\n- {new_class_b} implements {interface_b}\n- Both delegate to the original {component} during transition\n\n**Phase 3: Update consumers**\n- Audit all {num_consumers} call sites\n- Update imports and type annotations\n- Run full regression suite\n\n**Phase 4: Remove legacy code**\n- Delete the monolithic {component}\n- Update documentation\n- Bump the API version to {new_version}",
        ],
        "fill": lambda: {
            "component": random.choice(
                [
                    "AuthService",
                    "PaymentProcessor",
                    "NotificationEngine",
                    "DataPipeline",
                    "CacheManager",
                    "RateLimiter",
                    "EventBus",
                    "TaskScheduler",
                ]
            ),
            "language": random.choice(["Python", "TypeScript", "Go", "Rust", "Java"]),
            "error_type": random.choice(
                [
                    "NullPointerException",
                    "TypeError",
                    "ConnectionTimeout",
                    "DeadlockDetected",
                    "OutOfMemoryError",
                    "SegmentationFault",
                ]
            ),
            "action": random.choice(
                [
                    "processing batch requests",
                    "handling WebSocket connections",
                    "running database migrations",
                    "serializing protobuf messages",
                ]
            ),
            "file_path": f"src/{random.choice(['services', 'handlers', 'middleware', 'utils'])}/{random.choice(['auth', 'payment', 'notification', 'cache'])}_{random.choice(['handler', 'service', 'manager', 'processor'])}.{random.choice(['py', 'ts', 'go', 'rs'])}",
            "line_num": random.randint(50, 500),
            "version": f"{random.randint(1, 5)}.{random.randint(0, 20)}.{random.randint(0, 99)}",
            "framework": random.choice(
                ["FastAPI", "Express", "Gin", "Actix", "Spring Boot"]
            ),
            "method": random.choice(
                ["handle_request", "process_event", "execute_query", "validate_input"]
            ),
            "resource": random.choice(
                ["connection pool", "request queue", "session store", "token cache"]
            ),
            "data_structure": random.choice(
                ["HashMap", "ArrayList", "LinkedList", "ConcurrentQueue"]
            ),
            "old_type": random.choice(["dict", "list", "map", "array"]),
            "new_type": random.choice(
                [
                    "ConcurrentHashMap",
                    "SynchronizedList",
                    "AtomicReference",
                    "RWLock<HashMap>",
                ]
            ),
            "external_call": random.choice(
                ["database query", "HTTP request", "gRPC call", "Redis operation"]
            ),
            "test_framework": random.choice(
                ["pytest", "jest", "go test", "cargo test"]
            ),
            "test_util": random.choice(
                [
                    "threading fixtures",
                    "async test helpers",
                    "mock servers",
                    "test containers",
                ]
            ),
            "feature": random.choice(
                [
                    "real-time notifications",
                    "batch processing",
                    "audit logging",
                    "A/B testing",
                    "rate limiting",
                ]
            ),
            "layer": random.choice(["API", "service", "repository", "infrastructure"]),
            "pattern": random.choice(
                ["monolithic", "singleton", "factory", "repository"]
            ),
            "new_pattern": random.choice(
                ["event-driven", "CQRS", "hexagonal", "microservices"]
            ),
            "quality_attr": random.choice(
                ["scalability", "testability", "maintainability", "performance"]
            ),
            "responsibility_a": random.choice(
                ["authentication", "authorization", "validation", "serialization"]
            ),
            "responsibility_b": random.choice(
                ["caching", "logging", "metrics", "rate limiting"]
            ),
            "api_name": random.choice(["REST", "GraphQL", "gRPC", "WebSocket"]),
            "new_class_a": random.choice(
                ["AuthHandler", "ValidatorService", "SerializerFactory"]
            ),
            "new_class_b": random.choice(
                ["CacheLayer", "MetricsCollector", "RateLimitGuard"]
            ),
            "interface_a": random.choice(
                ["Authenticatable", "Validatable", "Serializable"]
            ),
            "interface_b": random.choice(["Cacheable", "Observable", "Limitable"]),
            "methods_a": random.choice(
                [
                    "authenticate(), refresh_token(), revoke()",
                    "validate(), sanitize(), normalize()",
                ]
            ),
            "methods_b": random.choice(
                ["get(), set(), invalidate()", "observe(), report(), reset()"]
            ),
            "num": random.randint(500, 3000),
            "num_consumers": random.randint(10, 100),
            "new_version": f"v{random.randint(2, 5)}.0.0",
            "column_type": random.choice(
                ["JSONB", "UUID", "TIMESTAMP", "TEXT", "BIGINT"]
            ),
            "table_name": random.choice(
                ["users", "events", "transactions", "audit_logs", "sessions"]
            ),
            "num_rows": random.randint(10, 500),
            "db_engine": random.choice(
                ["PostgreSQL 16", "MySQL 8", "ClickHouse", "CockroachDB"]
            ),
            "test_type": random.choice(
                ["integration", "e2e", "performance", "contract"]
            ),
            "test_name": random.choice(
                ["test_concurrent_writes", "test_auth_flow", "test_batch_processing"]
            ),
            "ci_env": random.choice(
                ["GitHub Actions", "CircleCI", "GitLab CI", "Jenkins"]
            ),
            "dependency": random.choice(
                ["numpy", "tensorflow", "postgres-driver", "protobuf"]
            ),
            "error_output": f"FAILED {random.choice(['test_auth', 'test_cache', 'test_api'])}::{random.choice(['test_concurrent', 'test_timeout', 'test_retry'])} - {random.choice(['AssertionError', 'TimeoutError', 'ConnectionRefused'])}: expected {random.randint(1, 100)} got {random.randint(1, 100)}",
            "code_block": f"def {random.choice(['handle', 'process', 'execute'])}(self, request):\n    with self._lock:\n        result = self._{random.choice(['cache', 'store', 'pool'])}.{random.choice(['get', 'fetch', 'acquire'])}(request.id)\n        if result is None:\n            result = self._fallback(request)\n        return result",
        },
    },
    "data_science": {
        "user_templates": [
            "I'm training a {model_type} model on {dataset_size} samples for {task}. The training loss plateaus at {loss_val} after {epochs} epochs. I've tried {optimizer} with learning rate {lr} and batch size {batch_size}. The model architecture has {layers} layers with {hidden_dim} hidden dimensions. Any suggestions for improving convergence?",
            "My {pipeline_type} pipeline is processing {data_volume} of {data_type} data daily. The current latency is {latency}ms p99 which exceeds our SLA of {sla}ms. The bottleneck seems to be in the {stage} stage where we're doing {operation}. We're running on {infrastructure} with {resources}.",
            "I need to build a {analysis_type} dashboard that shows {metric_a}, {metric_b}, and {metric_c} broken down by {dimension_a} and {dimension_b}. The underlying data is in {storage} with {schema_desc}. What's the best approach for sub-second query performance at {scale}?",
        ],
        "assistant_templates": [
            "Based on your training configuration, here are several approaches to improve convergence:\n\n**1. Learning Rate Schedule**\nYour current flat LR of {lr} is likely too high for the plateau phase. Try:\n- Cosine annealing: `CosineAnnealingLR(optimizer, T_max={t_max}, eta_min={eta_min})`\n- OneCycleLR with max_lr={max_lr} and {pct_start}% warmup\n\n**2. Architecture Adjustments**\n- Add residual connections between layers {layer_a} and {layer_b}\n- Replace BatchNorm with LayerNorm for better gradient flow\n- Consider {attention_type} attention mechanism for the {component}\n\n**3. Data Augmentation**\n- Apply {augmentation_a} with probability {aug_prob_a}\n- Add {augmentation_b} for regularization\n- Use mixup with alpha={mixup_alpha}\n\n**4. Training Tricks**\n- Gradient clipping at {clip_val}\n- Label smoothing with epsilon={smooth_eps}\n- Stochastic depth with drop rate {drop_rate}\n\nI'd prioritize the learning rate schedule first — that alone often breaks plateaus. Monitor both train and val loss to distinguish between underfitting and overfitting.",
        ],
        "fill": lambda: {
            "model_type": random.choice(
                ["transformer", "CNN", "GNN", "diffusion", "VAE", "GAN"]
            ),
            "dataset_size": f"{random.choice(['100K', '1M', '10M', '500K', '50M'])}",
            "task": random.choice(
                [
                    "image classification",
                    "text generation",
                    "anomaly detection",
                    "time series forecasting",
                    "recommendation",
                    "NER",
                ]
            ),
            "loss_val": f"{random.uniform(0.1, 2.5):.3f}",
            "epochs": random.randint(10, 200),
            "optimizer": random.choice(["AdamW", "SGD", "LAMB", "Adafactor"]),
            "lr": f"{random.choice([1e-3, 3e-4, 1e-4, 5e-5]):.1e}",
            "batch_size": random.choice([16, 32, 64, 128, 256]),
            "layers": random.randint(4, 48),
            "hidden_dim": random.choice([256, 512, 768, 1024, 2048]),
            "pipeline_type": random.choice(
                ["ETL", "streaming", "ML inference", "feature engineering"]
            ),
            "data_volume": random.choice(["500GB", "2TB", "10TB", "50TB"]),
            "data_type": random.choice(
                ["clickstream", "sensor", "transaction", "log", "genomic"]
            ),
            "latency": random.randint(100, 5000),
            "sla": random.randint(50, 500),
            "stage": random.choice(
                ["parsing", "transformation", "enrichment", "aggregation", "serving"]
            ),
            "operation": random.choice(
                [
                    "JSON deserialization",
                    "geospatial joins",
                    "window functions",
                    "regex extraction",
                ]
            ),
            "infrastructure": random.choice(
                ["Spark on EMR", "Flink on K8s", "Databricks", "BigQuery"]
            ),
            "resources": random.choice(
                [
                    "32 executors × 8 cores",
                    "16 GPU nodes",
                    "128GB RAM per node",
                    "auto-scaling 4-64 nodes",
                ]
            ),
            "analysis_type": random.choice(
                ["executive", "operational", "diagnostic", "predictive"]
            ),
            "metric_a": random.choice(
                ["conversion rate", "churn probability", "ARPU", "DAU/MAU ratio"]
            ),
            "metric_b": random.choice(
                ["p95 latency", "error rate", "throughput", "cache hit ratio"]
            ),
            "metric_c": random.choice(
                ["cost per query", "model accuracy", "data freshness", "SLA compliance"]
            ),
            "dimension_a": random.choice(
                ["region", "product line", "customer segment", "time period"]
            ),
            "dimension_b": random.choice(
                ["channel", "device type", "experiment variant", "team"]
            ),
            "storage": random.choice(
                ["ClickHouse", "BigQuery", "Snowflake", "Redshift", "DuckDB"]
            ),
            "schema_desc": random.choice(
                [
                    "star schema with 5 fact tables",
                    "denormalized wide table",
                    "nested JSON events",
                    "time-partitioned columnar",
                ]
            ),
            "scale": random.choice(
                [
                    "1B rows/day",
                    "100M events/hour",
                    "10TB compressed",
                    "50K concurrent users",
                ]
            ),
            "t_max": random.randint(50, 200),
            "eta_min": f"{random.choice([1e-6, 1e-7]):.1e}",
            "max_lr": f"{random.choice([1e-3, 3e-3, 5e-3]):.1e}",
            "pct_start": random.choice([10, 20, 30]),
            "layer_a": random.randint(1, 12),
            "layer_b": random.randint(13, 24),
            "attention_type": random.choice(
                ["multi-head", "flash", "grouped-query", "sliding window"]
            ),
            "component": random.choice(["encoder", "decoder", "cross-attention block"]),
            "augmentation_a": random.choice(
                ["random crop", "color jitter", "token masking", "time warping"]
            ),
            "augmentation_b": random.choice(
                ["cutout", "mixup", "CutMix", "SpecAugment"]
            ),
            "aug_prob_a": f"{random.uniform(0.1, 0.5):.1f}",
            "mixup_alpha": f"{random.uniform(0.1, 0.4):.1f}",
            "clip_val": f"{random.uniform(0.5, 2.0):.1f}",
            "smooth_eps": f"{random.uniform(0.05, 0.2):.2f}",
            "drop_rate": f"{random.uniform(0.1, 0.3):.1f}",
        },
    },
    "devops": {
        "user_templates": [
            "Our {service} service is experiencing {issue_type} in the {environment} environment. The {metric} spiked to {value} at {timestamp}. We're running {replicas} replicas on {platform} with {config_desc}. PagerDuty alert: {alert_name}. Can you help diagnose?",
            "I need to set up {infra_type} for our new {project_type} project. Requirements: {req_a}, {req_b}, {req_c}. Budget is ${budget}/month. We're currently on {cloud_provider} and need to support {traffic_desc}.",
        ],
        "assistant_templates": [
            "Based on the {metric} spike pattern and your configuration, this looks like a {root_cause}.\n\n**Immediate mitigation:**\n```bash\n{mitigation_command}\n```\n\n**Root cause analysis:**\nThe {component} is hitting the {limit} limit because {explanation}. When this happens, {cascade_effect}.\n\n**Permanent fix:**\n1. Increase {config_param} from {old_val} to {new_val}\n2. Add {monitoring_type} monitoring with threshold {threshold}\n3. Implement {pattern} to prevent cascading failures\n4. Update the {runbook} runbook with this scenario\n\n**Prevention:**\n- Set up {alert_type} alerts at {alert_threshold}% of the limit\n- Add circuit breaker with {cb_config}\n- Schedule load testing for {load_test_schedule}\n- Review capacity planning quarterly",
        ],
        "fill": lambda: {
            "service": random.choice(
                [
                    "payment-gateway",
                    "auth-service",
                    "notification-hub",
                    "data-ingestion",
                    "search-indexer",
                ]
            ),
            "issue_type": random.choice(
                [
                    "high latency",
                    "OOM kills",
                    "connection exhaustion",
                    "disk pressure",
                    "CPU throttling",
                ]
            ),
            "environment": random.choice(["production", "staging", "canary"]),
            "metric": random.choice(
                [
                    "p99 latency",
                    "error rate",
                    "memory usage",
                    "CPU utilization",
                    "connection count",
                ]
            ),
            "value": random.choice(
                [
                    "850ms (10x normal)",
                    "12% (threshold: 1%)",
                    "98% (OOM imminent)",
                    "100% (throttled)",
                    "maxed at 1000",
                ]
            ),
            "timestamp": f"2026-04-0{random.randint(1, 6)}T{random.randint(0, 23):02d}:{random.randint(0, 59):02d}:00Z",
            "replicas": random.randint(3, 50),
            "platform": random.choice(["EKS", "GKE", "AKS", "bare metal k8s"]),
            "config_desc": random.choice(
                [
                    "2 vCPU / 4GB RAM per pod",
                    "c5.2xlarge instances",
                    "spot instances with on-demand fallback",
                ]
            ),
            "alert_name": random.choice(
                [
                    "HighLatencyP99",
                    "ErrorRateCritical",
                    "PodOOMKilled",
                    "DiskPressureWarning",
                ]
            ),
            "root_cause": random.choice(
                [
                    "connection pool exhaustion",
                    "garbage collection storm",
                    "noisy neighbor",
                    "upstream dependency degradation",
                ]
            ),
            "mitigation_command": f"kubectl scale deployment/{random.choice(['payment', 'auth', 'api'])} --replicas={random.randint(10, 50)} -n {random.choice(['prod', 'services'])}",
            "component": random.choice(
                [
                    "database connection pool",
                    "HTTP client",
                    "message queue consumer",
                    "DNS resolver",
                ]
            ),
            "limit": random.choice(
                ["max_connections", "file descriptor", "thread pool", "memory"]
            ),
            "explanation": random.choice(
                [
                    "slow queries are holding connections longer than the TTL",
                    "a memory leak in the JSON parser accumulates over 72 hours",
                    "the upstream rate limiter is forcing retries",
                ]
            ),
            "cascade_effect": random.choice(
                [
                    "new requests queue up and eventually timeout",
                    "the OOM killer restarts pods causing a thundering herd",
                    "the circuit breaker opens and all traffic fails",
                ]
            ),
            "config_param": random.choice(
                ["max_pool_size", "memory_limit", "request_timeout", "max_retries"]
            ),
            "old_val": random.choice(["10", "512Mi", "30s", "3"]),
            "new_val": random.choice(["50", "2Gi", "10s", "5 with backoff"]),
            "monitoring_type": random.choice(
                ["connection pool saturation", "memory trend", "queue depth"]
            ),
            "threshold": random.choice(["80%", "90%", "95%"]),
            "pattern": random.choice(
                [
                    "circuit breaker",
                    "bulkhead",
                    "retry with jitter",
                    "graceful degradation",
                ]
            ),
            "runbook": random.choice(
                ["incident-response", "capacity-scaling", "dependency-failure"]
            ),
            "alert_type": random.choice(
                ["predictive", "threshold-based", "anomaly detection"]
            ),
            "alert_threshold": random.randint(70, 90),
            "cb_config": random.choice(
                ["5 failures in 60s → open for 30s", "error rate > 50% → open for 60s"]
            ),
            "load_test_schedule": random.choice(
                ["weekly off-peak", "before each release", "monthly chaos engineering"]
            ),
            "infra_type": random.choice(
                [
                    "CI/CD pipeline",
                    "monitoring stack",
                    "service mesh",
                    "secrets management",
                ]
            ),
            "project_type": random.choice(
                ["microservices", "ML platform", "data lake", "real-time analytics"]
            ),
            "req_a": random.choice(
                [
                    "zero-downtime deployments",
                    "multi-region HA",
                    "PCI compliance",
                    "SOC2 audit trail",
                ]
            ),
            "req_b": random.choice(
                [
                    "auto-scaling to 10x",
                    "sub-100ms P99",
                    "99.99% uptime SLA",
                    "end-to-end encryption",
                ]
            ),
            "req_c": random.choice(
                [
                    "GitOps workflow",
                    "blue-green deployments",
                    "canary with automatic rollback",
                ]
            ),
            "budget": random.choice(["5K", "15K", "50K", "100K"]),
            "cloud_provider": random.choice(["AWS", "GCP", "Azure", "hybrid"]),
            "traffic_desc": random.choice(
                [
                    "10K RPS steady, 100K RPS during peaks",
                    "1M events/min from IoT devices",
                    "500 concurrent ML inference requests",
                ]
            ),
        },
    },
}

AGENT_ARCHETYPES = [
    {
        "name": "code-assistant",
        "version": "2.1.0",
        "model": "claude-3-5-sonnet-20241022",
        "domain": "software_engineering",
        "provider": "anthropic",
    },
    {
        "name": "code-assistant",
        "version": "2.2.0-beta",
        "model": "claude-sonnet-4-20250514",
        "domain": "software_engineering",
        "provider": "anthropic",
    },
    {
        "name": "data-scientist",
        "version": "1.0.3",
        "model": "gpt-4o",
        "domain": "data_science",
        "provider": "openai",
    },
    {
        "name": "data-scientist",
        "version": "1.1.0",
        "model": "gpt-4o-2024-11-20",
        "domain": "data_science",
        "provider": "openai",
    },
    {
        "name": "sre-bot",
        "version": "3.0.0",
        "model": "claude-3-5-sonnet-20241022",
        "domain": "devops",
        "provider": "anthropic",
    },
    {
        "name": "sre-bot",
        "version": "3.1.0",
        "model": "gemini-2.0-flash",
        "domain": "devops",
        "provider": "google",
    },
    {
        "name": "infra-advisor",
        "version": "1.0.0",
        "model": "o4-mini",
        "domain": "devops",
        "provider": "openai",
    },
]


def _generate_message(domain_name: str, role: str) -> str:
    """Generate a realistic message for a given domain and role."""
    domain = DOMAINS[domain_name]
    templates = (
        domain["user_templates"] if role == "user" else domain["assistant_templates"]
    )
    template = random.choice(templates)
    fills = domain["fill"]()
    try:
        return template.format(**fills)
    except KeyError:
        return template  # fallback if template var missing


def _generate_conversation(agent: dict, num_turns: int) -> dict:
    """Generate a conversation with growing message history (pre-compaction simulation)."""
    conv_id = uuid.uuid4().hex[:24]
    history: list[dict] = []
    turns = []

    # System instructions
    system_prompts = [
        f"You are {agent['name']} v{agent['version']}, an AI assistant specializing in {agent['domain'].replace('_', ' ')}.",
        "Always provide actionable, specific advice with code examples when relevant.",
        "If you're unsure about something, say so and suggest how to verify.",
    ]

    for turn_idx in range(num_turns):
        # Generate new messages for this turn
        user_msg = _generate_message(agent["domain"], "user")
        assistant_msg = _generate_message(agent["domain"], "assistant")

        # Add to growing history
        history.append({"role": "user", "content": user_msg})
        history.append({"role": "assistant", "content": assistant_msg})

        # Build turn with FULL history (simulating pre-compaction)
        # Each turn carries all previous messages plus the new ones
        turn_messages = [{"role": "user", "content": user_msg}]
        # The assistant response
        turn_messages.append({"role": "assistant", "content": assistant_msg})

        # Simulate token counts based on message lengths
        total_chars = sum(len(m["content"]) for m in history)
        input_tokens = int(total_chars * 0.3)  # rough chars-to-tokens
        output_tokens = int(len(assistant_msg) * 0.3)

        turns.append(
            {
                "messages": [
                    # Full history as input (pre-compaction behavior)
                    *[
                        {"role": m["role"], "content": m["content"]}
                        for m in history[:-1]
                    ],
                    {"role": "assistant", "content": assistant_msg},
                ],
                "agent_name": agent["name"],
                "model": agent["model"],
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "system_instructions": system_prompts if turn_idx == 0 else [],
            }
        )

    return {
        "conversation_id": conv_id,
        "conversation_name": f"{agent['domain']} session {conv_id[:8]}",
        "provider_name": agent.get("provider", ""),
        "agent_name": agent["name"],
        "turns": turns,
    }


def _post(
    session: requests.Session, url: str, payload: dict, auth, project_id: str
) -> dict:
    """POST and return response."""
    r = session.post(
        f"{url}/agents/conversations/ingest",
        json=payload,
        params={"project_id": project_id},
        auth=auth,
        timeout=60,
    )
    if r.status_code != 200:
        return {"error": r.status_code, "detail": r.text[:200]}
    return r.json()


def main():
    parser = argparse.ArgumentParser(description="Large-message load generator")
    parser.add_argument(
        "--conversations", type=int, default=50, help="Number of conversations"
    )
    parser.add_argument(
        "--turns-per-conv",
        type=int,
        default=10,
        help="Turns per conversation (history grows each turn)",
    )
    parser.add_argument(
        "--concurrency", type=int, default=5, help="Concurrent upload threads"
    )
    parser.add_argument(
        "--project", type=str, default="", help="W&B project (entity/project)"
    )
    args = parser.parse_args()

    entity = os.environ.get("WANDB_ENTITY", "ben-urmomsclothes")
    project = args.project or f"{entity}/genai-otel-test"
    server = os.environ.get("WF_TRACE_SERVER_URL", "http://localhost:6345")
    api_key = os.environ.get("WANDB_API_KEY", "")
    auth = ("api", api_key) if api_key else None

    print("Large Message Load Generator")
    print(f"  Server:        {server}")
    print(f"  Project:       {project}")
    print(f"  Conversations: {args.conversations}")
    print(f"  Turns/conv:    {args.turns_per_conv}")
    print(f"  Concurrency:   {args.concurrency}")

    # Estimate data volume
    avg_msg_size = 800  # chars per message
    total_messages = (
        args.conversations * args.turns_per_conv * (args.turns_per_conv + 1)
    )  # growing history
    est_data_mb = total_messages * avg_msg_size / 1_000_000
    print(f"  Est. data:     ~{est_data_mb:.0f} MB of message text")
    print()

    # Generate conversations
    print("Generating conversations...")
    conversations = []
    for _ in range(args.conversations):
        agent = random.choice(AGENT_ARCHETYPES)
        conv = _generate_conversation(agent, args.turns_per_conv)
        conv["project_id"] = project
        conversations.append(conv)

    print(f"Generated {len(conversations)} conversations")

    # Upload with concurrency
    print(f"\nUploading ({args.concurrency} threads)...")
    session = requests.Session()
    start = time.time()
    total_spans = 0
    errors = 0

    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = {
            pool.submit(_post, session, server, conv, auth, project): i
            for i, conv in enumerate(conversations)
        }
        for future in as_completed(futures):
            idx = futures[future]
            try:
                result = future.result()
                if "error" in result:
                    errors += 1
                    if errors <= 5:
                        print(f"  [{idx}] ERROR {result['error']}: {result['detail']}")
                else:
                    total_spans += result.get("span_count", 0)
                    if (idx + 1) % max(1, args.conversations // 10) == 0:
                        elapsed = time.time() - start
                        rate = (idx + 1) / elapsed
                        print(
                            f"  [{idx + 1}/{args.conversations}] {total_spans} spans, {rate:.1f} conv/s"
                        )
            except Exception as e:
                errors += 1
                if errors <= 5:
                    print(f"  [{idx}] EXCEPTION: {e}")

    elapsed = time.time() - start
    print(f"\nDone in {elapsed:.1f}s")
    print(f"  Conversations: {args.conversations - errors} succeeded, {errors} failed")
    print(f"  Total spans:   {total_spans}")
    print(
        f"  Rate:          {(args.conversations - errors) / elapsed:.1f} conv/s, {total_spans / elapsed:.0f} spans/s"
    )

    # Suggest search queries
    print("\nSearch test queries:")
    print(
        f"  curl -s -X POST {server}/agents/search -H 'Content-Type: application/json' \\"
    )
    print(f"    -u 'api:{api_key[:20]}...' \\")
    print(f'    -d \'{{"project_id":"{project}","query":"connection pool"}}\'')


if __name__ == "__main__":
    main()
