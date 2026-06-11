import pytest


@pytest.fixture
def vcr_config() -> dict[str, object]:
    """VCR passthrough for infra: clickhouse (localhost) and the wandb API bypass cassettes; only provider calls replay."""
    return {"ignore_localhost": True, "ignore_hosts": ["api.wandb.ai"]}
