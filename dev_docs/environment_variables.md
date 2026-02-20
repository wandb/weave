# Environment Variables Audit

This document inventories environment variables referenced in repository code paths.

## Method

- Scanned Python and TypeScript for `os.getenv`, `os.environ`, `process.env`, `monkeypatch.setenv`, and `patch.dict(os.environ, ...)` patterns.
- Added dynamic cases that are not string-literal lookups (notably `WEAVE_*` settings in `weave/trace/settings.py`, nox passthrough lists, and ClickHouse async insert env keys).
- Included references used in runtime, tests, CI scripts, and release tooling.

## Variables

### Runtime

| Variable | What it does | Primary reference |
| --- | --- | --- |
| `ALL_PROXY` | Fallback proxy URL used for outbound HTTP requests when `HTTPS_PROXY`/`HTTP_PROXY` are not set. | `weave/utils/http_requests.py:168` |
| `HTTPS_PROXY` | HTTPS proxy URL for outbound HTTP requests. | `weave/utils/http_requests.py:168` |
| `HTTP_PROXY` | HTTP proxy URL for outbound HTTP requests. | `weave/utils/http_requests.py:168` |
| `NETRC` | Path override for the netrc file when resolving credentials. | `weave/compat/wandb/util/netrc.py:263` |
| `WANDB_API_KEY` | W&B API key for authentication (Python and Node clients). | `weave/trace/env.py:74` |
| `WANDB_APP_URL` | Override for W&B app URL in compatibility helpers. | `weave/compat/wandb/wandb_thin/util.py:5` |
| `WANDB_BASE_URL` | Base URL for W&B API host selection. | `weave/trace/env.py:50` |
| `WANDB_CONFIG_DIR` | Directory containing W&B settings files. | `weave/trace/env.py:40` |
| `WANDB_ENTITY` | Default W&B entity used when project name omits explicit entity. | `weave/trace/weave_init.py:48` |
| `WANDB_PUBLIC_BASE_URL` | Public frontend URL override used to derive trace-server base URL. | `weave/trace/env.py:54` |
| `WEAVE_CAPTURE_CLIENT_INFO` | Controls inclusion of client metadata (Python/SDK version) in traces. | `weave/trace/settings.py:106` |
| `WEAVE_CAPTURE_CODE` | Controls whether op source code is captured with traces. | `weave/trace/settings.py:68` |
| `WEAVE_CAPTURE_SYSTEM_INFO` | Controls inclusion of system metadata (OS/version) in traces. | `weave/trace/settings.py:109` |
| `WEAVE_CLIENT_PARALLELISM` | Sets background worker concurrency; `0` forces synchronous behavior. | `weave/trace/settings.py:112` |
| `WEAVE_DEBUG_HTTP` | Enables verbose HTTP request/response logging when set to `1`. | `weave/utils/http_requests.py:141` |
| `WEAVE_DISABLED` | Disables Weave tracing when truthy. | `weave/trace/settings.py:39` |
| `WEAVE_DISPLAY_VIEWER` | Selects display backend (`auto`, `rich`, `print`). | `weave/trace/settings.py:62` |
| `WEAVE_ENABLE_DISK_FALLBACK` | Writes dropped/failed queue items to disk when enabled. | `weave/trace/settings.py:185` |
| `WEAVE_HTTP_TIMEOUT` | Global HTTP timeout (seconds) for Weave HTTP calls. | `weave/trace/settings.py:204` |
| `WEAVE_LOG_LEVEL` | Log level for Weave logging (for example `INFO`, `ERROR`). | `weave/trace/settings.py:52` |
| `WEAVE_MAX_CALLS_QUEUE_SIZE` | Maximum buffered call queue size before fallback/drop behavior. | `weave/trace/settings.py:162` |
| `WEAVE_PARALLELISM` | Parallelism level for Weave background execution in Python client helpers. | `weave/trace/env.py:45` |
| `WEAVE_PRINT_CALL_LINK` | Controls whether call links are printed to terminal output. | `weave/trace/settings.py:45` |
| `WEAVE_REDACT_PII` | Enables PII redaction of trace payloads. | `weave/trace/settings.py:86` |
| `WEAVE_REDACT_PII_EXCLUDE_FIELDS` | Comma-separated list of entities to exclude from PII redaction. | `weave/trace/settings.py:104` |
| `WEAVE_REDACT_PII_FIELDS` | Comma-separated list of fields/entities to redact when PII redaction is enabled. | `weave/trace/settings.py:97` |
| `WEAVE_RETRY_MAX_ATTEMPTS` | Maximum number of retry attempts. | `weave/trace/settings.py:176` |
| `WEAVE_RETRY_MAX_INTERVAL` | Maximum retry backoff interval (seconds). | `weave/trace/settings.py:169` |
| `WEAVE_SCORERS_DIR` | Directory used for downloaded scorer model artifacts. | `weave/trace/settings.py:154` |
| `WEAVE_SENTRY_ENV` | Sentry environment label override for Weave telemetry. | `weave/telemetry/trace_sentry.py:79` |
| `WEAVE_SERVER_CACHE_DIR` | Directory path for server-response cache files. | `weave/trace/settings.py:146` |
| `WEAVE_SERVER_CACHE_SIZE_LIMIT` | Maximum size (bytes) for the server-response cache. | `weave/trace/settings.py:138` |
| `WEAVE_USE_CALLS_COMPLETE` | Uses calls_complete write path instead of call_start/call_end endpoints. | `weave/trace/settings.py:227` |
| `WEAVE_USE_PARALLEL_TABLE_UPLOAD` | Enables parallel chunked upload path for large tables. | `weave/trace/settings.py:194` |
| `WEAVE_USE_SERVER_CACHE` | Enables on-disk caching of server responses. | `weave/trace/settings.py:130` |
| `WEAVE_USE_STAINLESS_SERVER` | Uses Stainless-generated trace server client when enabled. | `weave/trace/settings.py:213` |
| `WF_TRACE_SERVER_URL` | Explicit trace server URL override (Python and Node clients). | `weave/trace/env.py:66` |

### Runtime (Trace Server)

| Variable | What it does | Primary reference |
| --- | --- | --- |
| `INFERENCE_SERVICE_BASE_URL` | Base URL for the inference service used by the trace server. | `weave/trace_server/environment.py:320` |
| `KAFKA_BROKER_HOST` | Kafka broker host for trace-server messaging. | `weave/trace_server/environment.py:11` |
| `KAFKA_BROKER_PORT` | Kafka broker port for trace-server messaging. | `weave/trace_server/environment.py:16` |
| `KAFKA_CLIENT_PASSWORD` | Kafka client password. | `weave/trace_server/environment.py:26` |
| `KAFKA_CLIENT_USER` | Kafka client username. | `weave/trace_server/environment.py:21` |
| `KAFKA_PARTITION_BY_PROJECT_ID` | When true, partitions Kafka messages by project_id. | `weave/trace_server/environment.py:49` |
| `KAFKA_PRODUCER_MAX_BUFFER_SIZE` | Max buffered Kafka producer messages; invalid values are ignored. | `weave/trace_server/environment.py:31` |
| `PROJECT_VERSION_MODE` | Controls trace server read/write routing mode between legacy and calls_complete tables. | `weave/trace_server/project_version/types.py:47` |
| `SCORING_WORKER_CHECK_CANCELLATION` | When true, scoring worker checks cancellation on each poll for faster shutdown (mainly useful in tests). | `weave/trace_server/environment.py:77` |
| `SCORING_WORKER_KAFKA_CONSUMER_GROUP_ID` | Optional scoring worker Kafka consumer-group override. | `weave/trace_server/environment.py:88` |
| `WEAVE_ENABLE_ONLINE_EVAL` | Trace server toggle for enabling online evaluation flow. | `weave/trace_server/environment.py:57` |
| `WF_CLICKHOUSE_ASYNC_INSERT_BUSY_TIMEOUT_MAX_MS` | Upper bound adaptive async-insert flush timeout (ms). | `weave/trace_server/environment.py:196` |
| `WF_CLICKHOUSE_ASYNC_INSERT_BUSY_TIMEOUT_MIN_MS` | Lower bound/initial adaptive async-insert flush timeout (ms). | `weave/trace_server/environment.py:175` |
| `WF_CLICKHOUSE_DATABASE` | ClickHouse database name. | `weave/trace_server/environment.py:116` |
| `WF_CLICKHOUSE_HOST` | ClickHouse host for trace server backend. | `weave/trace_server/environment.py:96` |
| `WF_CLICKHOUSE_MAX_EXECUTION_TIME` | Per-query ClickHouse max execution time override. | `weave/trace_server/environment.py:156` |
| `WF_CLICKHOUSE_MAX_MEMORY_USAGE` | Per-query ClickHouse max memory usage override. | `weave/trace_server/environment.py:144` |
| `WF_CLICKHOUSE_PASS` | ClickHouse password. | `weave/trace_server/environment.py:111` |
| `WF_CLICKHOUSE_PORT` | ClickHouse HTTP port. | `weave/trace_server/environment.py:101` |
| `WF_CLICKHOUSE_REPLICATED` | Enables replicated ClickHouse tables when truthy. | `weave/trace_server/environment.py:121` |
| `WF_CLICKHOUSE_REPLICATED_CLUSTER` | Replication cluster name for ClickHouse. | `weave/trace_server/environment.py:131` |
| `WF_CLICKHOUSE_REPLICATED_PATH` | Replication path for replicated ClickHouse tables. | `weave/trace_server/environment.py:126` |
| `WF_CLICKHOUSE_USER` | ClickHouse username. | `weave/trace_server/environment.py:106` |
| `WF_CLICKHOUSE_USE_DISTRIBUTED_TABLES` | Enables distributed tables on top of replicated tables. | `weave/trace_server/environment.py:137` |
| `WF_FILE_STORAGE_AWS_ACCESS_KEY_ID` | AWS S3 access key ID for BYOB storage. | `weave/trace_server/environment.py:243` |
| `WF_FILE_STORAGE_AWS_KMS_KEY` | AWS KMS key identifier for encryption settings. | `weave/trace_server/environment.py:258` |
| `WF_FILE_STORAGE_AWS_REGION` | AWS region for file storage operations. | `weave/trace_server/environment.py:263` |
| `WF_FILE_STORAGE_AWS_SECRET_ACCESS_KEY` | AWS S3 secret access key for BYOB storage. | `weave/trace_server/environment.py:248` |
| `WF_FILE_STORAGE_AWS_SESSION_TOKEN` | AWS session token for temporary credentials. | `weave/trace_server/environment.py:253` |
| `WF_FILE_STORAGE_AZURE_ACCESS_KEY` | Azure storage account access key auth option. | `weave/trace_server/environment.py:273` |
| `WF_FILE_STORAGE_AZURE_ACCOUNT_URL` | Optional Azure account URL override. | `weave/trace_server/environment.py:278` |
| `WF_FILE_STORAGE_AZURE_CONNECTION_STRING` | Azure Blob Storage connection string auth option. | `weave/trace_server/environment.py:268` |
| `WF_FILE_STORAGE_GCP_CREDENTIALS_JSON_B64` | Base64-encoded GCP service account JSON for GCS access. | `weave/trace_server/environment.py:283` |
| `WF_FILE_STORAGE_PROJECT_ALLOW_LIST` | Comma-separated allowed project IDs (or `*`) for file storage. | `weave/trace_server/environment.py:228` |
| `WF_FILE_STORAGE_PROJECT_RAMP_PCT` | Rollout percentage (0-100) of projects using external file storage. | `weave/trace_server/environment.py:296` |
| `WF_FILE_STORAGE_URI` | Storage backend URI (for example `s3://...`, `gs://...`, `az://...`). | `weave/trace_server/environment.py:214` |
| `WF_SCORING_WORKER_BATCH_SIZE` | Batch size for scoring worker consumption. | `weave/trace_server/environment.py:62` |
| `WF_SCORING_WORKER_BATCH_TIMEOUT` | Batch timeout (seconds) for scoring worker flushes. | `weave/trace_server/environment.py:67` |

### Integrations

| Variable | What it does | Primary reference |
| --- | --- | --- |
| `AWS_REGION_NAME` | AWS region override used when resolving Bedrock inference profile ARNs. | `weave/integrations/bedrock/bedrock_sdk.py:106` |
| `MCP_TRACE_LIST_OPERATIONS` | Opt-in toggle to also trace MCP `list_*` operations (client and server patchers). | `weave/integrations/mcp/mcp_client.py:201` |
| `WANDB_DISABLE_WEAVE` | Disables automatic weave init behavior from the wandb init hook. | `weave/integrations/wandb/wandb.py:10` |
| `WEAVE_DSPY_HIDE_HISTORY` | Removes `history` from DSPy-traced payloads when truthy. | `weave/integrations/dspy/dspy_utils.py:24` |
| `WEAVE_IMPLICITLY_PATCH_INTEGRATIONS` | Enables/disables automatic import-hook patching for supported integrations. | `weave/trace/settings.py:80` |
| `WEAVE_TRACE_LANGCHAIN` | LangChain integration tracing toggle managed by the LangChain patcher. | `weave/integrations/langchain/langchain.py:424` |
| `ANTHROPIC_API_KEY` | Anthropic API key used by integration tests and/or nox shards. | `noxfile.py:168` |
| `CEREBRAS_API_KEY` | Cerebras API key used by integration tests and/or nox shards. | `tests/integrations/cerebras/cerebras_test.py:27` |
| `COHERE_API_KEY` | Cohere API key used by integration tests and/or nox shards. | `tests/integrations/cohere/cohere_test.py:31` |
| `GEMINI_API_KEY` | Gemini API key used by integration tests and/or nox shards. | `noxfile.py:167` |
| `GOOGLE_API_KEY` | Google API key used by integration tests and/or nox shards. | `noxfile.py:157` |
| `GOOGLE_GENAI_KEY` | Google GenAI API key used by Google GenAI integration tests. | `tests/integrations/google_genai/test_google_genai.py:40` |
| `GROQ_API_KEY` | Groq API key used by integration tests and/or nox shards. | `tests/integrations/groq/groq_test.py:36` |
| `HUGGINGFACE_API_KEY` | Huggingface API key used by integration tests and/or nox shards. | `tests/integrations/huggingface/test_huggingface_inference_client.py:19` |
| `MISTRAL_API_KEY` | Mistral API key used by integration tests and/or nox shards. | `noxfile.py:169` |
| `NOTDIAMOND_API_KEY` | Notdiamond API key used by integration tests and/or nox shards. | `tests/integrations/notdiamond/custom_router_test.py:79` |
| `NVIDIA_API_KEY` | Nvidia API key used by integration tests and/or nox shards. | `noxfile.py:161` |
| `OPENAI_API_KEY` | Openai API key used by integration tests and/or nox shards. | `noxfile.py:170` |
| `SERPAPI_API_KEY` | Serpapi API key used by integration tests and/or nox shards. | `tests/integrations/smolagents/test_smolagents.py:127` |

### Test

| Variable | What it does | Primary reference |
| --- | --- | --- |
| `CI` | Generic CI indicator used by tests and nox to adjust behavior in CI environments. | `tests/integrations/langchain/langchain_test.py:402` |
| `DD_ENV` | Datadog environment label; tests temporarily override it to isolate tracing behavior. | `tests/conftest.py:100` |
| `DD_TRACE_ENABLED` | Datadog tracing toggle; tests set this to avoid ddtrace side effects. | `tests/conftest.py:101` |
| `PYTEST_CURRENT_TEST` | Pytest-provided current test identifier, used by fixtures for per-test cache isolation. | `tests/conftest.py:183` |
| `PYTHONPATH` | Python module search path adjusted in tests/subprocesses to import local repo code. | `tests/integrations/mcp/mcp_test.py:62` |
| `WANDB_ERROR_REPORTING` | W&B error-reporting toggle (set in tests to avoid external reporting). | `tests/conftest.py:29` |
| `WB_SERVER_HOST` | Nox pass-through variable for tests that target custom W&B server hosts. | `noxfile.py:149` |
| `WEAVE_SERVER_DISABLE_ECOSYSTEM` | Nox pass-through variable to disable ecosystem checks in test runs. | `noxfile.py:151` |

### CI

| Variable | What it does | Primary reference |
| --- | --- | --- |
| `GITHUB_REPOSITORY` | Repository slug used by GitHub automation scripts when calling the GitHub API. | `.github/scripts/validate_docs_coverage.py:18` |
| `GITHUB_TOKEN` | GitHub API token for automation scripts (docs coverage PR commenter and Slack digest). | `.github/scripts/validate_docs_coverage.py:13` |
| `PR_BODY` | Pull request body consumed by docs coverage validation workflow script. | `.github/scripts/validate_docs_coverage.py:121` |
| `PR_NUMBER` | Pull request number consumed by docs coverage validation workflow script. | `.github/scripts/validate_docs_coverage.py:19` |
| `PR_TITLE` | Pull request title consumed by docs coverage validation workflow script. | `.github/scripts/validate_docs_coverage.py:120` |

### Dev / Script

| Variable | What it does | Primary reference |
| --- | --- | --- |
| `SLACK_TOKEN` | Slack API token used by `scripts/slack_digest.py`. | `scripts/slack_digest.py:871` |
| `TWINE_API_KEY` | PyPI API token used by release publishing script; mapped into twine credentials. | `scripts/publish_pypi_release.py:115` |
| `TWINE_PASSWORD` | Twine upload password passed to `twine upload` (set by script from API key when available). | `scripts/publish_pypi_release.py:103` |
| `TWINE_TEST_API_KEY` | TestPyPI API token used by release publishing script; mapped into twine credentials. | `scripts/publish_pypi_release.py:102` |
| `TWINE_TEST_PASSWORD` | TestPyPI password used by release publishing script when token auth is not used. | `scripts/publish_pypi_release.py:107` |
| `TWINE_TEST_USERNAME` | TestPyPI username used by release publishing script when token auth is not used. | `scripts/publish_pypi_release.py:105` |
| `TWINE_USERNAME` | Twine upload username passed to `twine upload` (set by script from API key when available). | `scripts/publish_pypi_release.py:104` |

## Dynamic Secret Name Lookups

- Some test helpers intentionally resolve secrets dynamically via a runtime `secret_name` string (for example in `tests/integrations/litellm/test_actions_lifecycle_llm_judge.py` and `tests/trace_server/test_custom_provider.py`).
- Those paths can read any env var name provided by the test/server payload, so they are not limited to a fixed compile-time set.
