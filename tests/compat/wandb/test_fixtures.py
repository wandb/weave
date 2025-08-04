"""Shared test fixtures and constants for wandb compatibility tests."""

from dataclasses import dataclass


@dataclass
class HostAndBaseURL:
    """Data class for host and base URL pairs."""

    host: str
    base_url: str


# Constants for test parameterization
all_valid_keys = ["valid-saas", "valid-onprem"]
all_invalid_keys = [
    "invalid-too-short",
    "invalid-too-long",
    "invalid-onprem-too-short",
    "invalid-onprem-too-long",
]

# Constants for host parameterization
all_hosts = ["saas", "aws", "gcp", "azure", "onprem"]
