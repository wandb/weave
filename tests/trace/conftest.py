"""Shared fixtures for trace tests."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from tests.trace.test_utils import FailingSaveType, failing_load, failing_save
from weave.trace.serialization import serializer
from weave.trace.settings import UserSettings
from weave.trace.weave_client import WeaveClient


@dataclass
class DigestParamsClient:
    client: WeaveClient
    enable_client_side_digests: bool


@pytest.fixture(
    params=[
        pytest.param(False, id="client_side_digests_off"),
        pytest.param(True, id="client_side_digests_on"),
    ],
)
def digest_params_client(client_creator, request) -> DigestParamsClient:
    """Yield a DigestParamsClient for both digest modes."""
    with client_creator(
        settings=UserSettings(enable_client_side_digests=request.param)
    ) as client:
        yield DigestParamsClient(client=client, enable_client_side_digests=request.param)


@pytest.fixture
def failing_serializer():
    """Register a serializer that always fails, and clean up after the test."""
    serializer.register_serializer(FailingSaveType, failing_save, failing_load)
    yield FailingSaveType
    serializer.SERIALIZERS[:] = [
        s for s in serializer.SERIALIZERS if s.target_class is not FailingSaveType
    ]
