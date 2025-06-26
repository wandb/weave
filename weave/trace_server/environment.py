import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# Kafka Settings


def wf_kafka_broker_host() -> str:
    """The host of the kafka broker."""
    return os.environ.get("WF_KAFKA_BROKER_HOST", "localhost")


def wf_kafka_broker_port() -> int:
    """The port of the kafka broker."""
    return int(os.environ.get("WF_KAFKA_BROKER_PORT", 9092))


# Scoring worker settings


def wf_enable_online_eval() -> bool:
    """Whether to enable online evaluation."""
    return os.environ.get("WEAVE_ENABLE_ONLINE_EVAL", "false").lower() == "true"


def wf_scoring_worker_batch_size() -> int:
    """The batch size for the scoring worker."""
    return int(os.environ.get("WF_SCORING_WORKER_BATCH_SIZE", 100))


def wf_scoring_worker_batch_timeout() -> int:
    """The timeout for the scoring worker."""
    return int(os.environ.get("WF_SCORING_WORKER_BATCH_TIMEOUT", 5))


# Clickhouse Settings


def wf_clickhouse_host() -> str:
    """The host of the clickhouse server."""
    return os.environ.get("WF_CLICKHOUSE_HOST", "localhost")


def wf_clickhouse_port() -> int:
    """The port of the clickhouse server."""
    return int(os.environ.get("WF_CLICKHOUSE_PORT", 8123))


def wf_clickhouse_user() -> str:
    """The user of the clickhouse server."""
    return os.environ.get("WF_CLICKHOUSE_USER", "default")


def wf_clickhouse_pass() -> str:
    """The password of the clickhouse server."""
    return os.environ.get("WF_CLICKHOUSE_PASS", "")


def wf_clickhouse_database() -> str:
    """The name of the clickhouse database."""
    return os.environ.get("WF_CLICKHOUSE_DATABASE", "default")


def wf_clickhouse_max_memory_usage() -> Optional[int]:
    """The maximum memory usage for the clickhouse server."""
    mem = os.environ.get("WF_CLICKHOUSE_MAX_MEMORY_USAGE")
    if mem is None:
        return None
    try:
        return int(mem)
    except ValueError as e:
        logger.exception(
            f"WF_CLICKHOUSE_MAX_MEMORY_USAGE value '{mem}' is not a valid. Error: {str(e)}"
        )
        return None


def wf_clickhouse_max_execution_time() -> Optional[int]:
    """The maximum execution time for the clickhouse server."""
    time = os.environ.get("WF_CLICKHOUSE_MAX_EXECUTION_TIME")
    if time is None:
        return None
    try:
        return int(time)
    except ValueError as e:
        logger.exception(
            f"WF_CLICKHOUSE_MAX_EXECUTION_TIME value '{time}' is not a valid. Error: {str(e)}"
        )
        return None


# BYOB Settings


def wf_file_storage_uri() -> Optional[str]:
    """The storage bucket URI."""
    return os.environ.get("WF_FILE_STORAGE_URI")


def wf_file_storage_project_allow_list() -> Optional[list[str]]:
    """Get the list of project IDs allowed to use file storage.

    Returns:
        Optional[list[str]]: A list of project IDs that are allowed to use file storage.
            Returns None if no allow list is configured.

    Raises:
        ValueError: If the allow list environment variable is set but contains invalid data.
            The value must be a comma-separated list of non-empty project IDs.
    """
    allow_list = os.environ.get("WF_FILE_STORAGE_PROJECT_ALLOW_LIST")
    if allow_list is None:
        return None
    try:
        project_ids = [pid.strip() for pid in allow_list.split(",") if pid.strip()]
    except Exception as e:
        raise ValueError(
            f"WF_FILE_STORAGE_PROJECT_ALLOW_LIST is not a valid comma-separated list: {allow_list}. Error: {str(e)}"
        ) from e

    return project_ids


def wf_storage_bucket_aws_access_key_id() -> Optional[str]:
    """The AWS access key ID."""
    return os.environ.get("WF_FILE_STORAGE_AWS_ACCESS_KEY_ID")


def wf_storage_bucket_aws_secret_access_key() -> Optional[str]:
    """The AWS secret access key."""
    return os.environ.get("WF_FILE_STORAGE_AWS_SECRET_ACCESS_KEY")


def wf_storage_bucket_aws_session_token() -> Optional[str]:
    """The AWS session token."""
    return os.environ.get("WF_FILE_STORAGE_AWS_SESSION_TOKEN")


def wf_storage_bucket_aws_kms_key() -> Optional[str]:
    """The AWS KMS key."""
    return os.environ.get("WF_FILE_STORAGE_AWS_KMS_KEY")


def wf_storage_bucket_aws_region() -> Optional[str]:
    """The AWS region."""
    return os.environ.get("WF_FILE_STORAGE_AWS_REGION")


def wf_storage_bucket_azure_connection_string() -> Optional[str]:
    """The Azure connection string."""
    return os.environ.get("WF_FILE_STORAGE_AZURE_CONNECTION_STRING")


def wf_storage_bucket_azure_access_key() -> Optional[str]:
    """The Azure credential."""
    return os.environ.get("WF_FILE_STORAGE_AZURE_ACCESS_KEY")


def wf_storage_bucket_azure_account_url() -> Optional[str]:
    """The Azure account url (optional override)."""
    return os.environ.get("WF_FILE_STORAGE_AZURE_ACCOUNT_URL")


def wf_storage_bucket_gcp_credentials_json_b64() -> Optional[str]:
    """The GCP credentials JSON string (base64 encoded)."""
    return os.environ.get("WF_FILE_STORAGE_GCP_CREDENTIALS_JSON_B64")


def wf_file_storage_project_ramp_pct() -> Optional[int]:
    """The percentage of projects that should use file storage (0-100).

    Returns:
        Optional[int]: The percentage of projects that should use file storage.
            Returns None if not configured.

    Raises:
        ValueError: If the value is not a valid integer between 0 and 100.
    """
    pct_str = os.environ.get("WF_FILE_STORAGE_PROJECT_RAMP_PCT")
    if not pct_str:
        return None

    try:
        pct = int(pct_str)
    except ValueError as e:
        raise ValueError(
            f"WF_FILE_STORAGE_PROJECT_RAMP_PCT is not a valid integer: {pct_str}. Error: {str(e)}"
        ) from e

    if pct < 0 or pct > 100:
        raise ValueError(
            f"WF_FILE_STORAGE_PROJECT_RAMP_PCT must be between 0 and 100, got {pct}"
        )

    return pct


# Inference Service Settings


def inference_service_base_url() -> str:
    """The base URL for the inference service."""
    return os.environ.get(
        "INFERENCE_SERVICE_BASE_URL", "https://api.inference.wandb.ai/v1"
    )
