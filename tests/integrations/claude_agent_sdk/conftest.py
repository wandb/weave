"""Conftest for Claude Agent SDK integration tests.

Provides a ReplayTransport that replays pre-recorded message sequences
from JSON cassette files, analogous to VCR for HTTP-based integrations.
The Claude Agent SDK communicates via subprocess (not HTTP), so we
implement our own recording/replay at the Transport layer.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import anyio
from claude_agent_sdk._internal.transport import Transport

CASSETTES_DIR = Path(__file__).parent / "cassettes"


class ReplayTransport(Transport):
    """A Transport that replays pre-recorded JSON messages from a cassette file.

    Handles the SDK's control protocol (initialize handshake) automatically,
    then yields recorded messages from the cassette.
    """

    def __init__(self, messages: list[dict[str, Any]]) -> None:
        self._messages = messages
        self._connected = False
        self._pending_control_ids: list[str] = []
        self._control_event = anyio.Event()

    async def connect(self) -> None:
        self._connected = True

    async def write(self, data: str) -> None:
        parsed = json.loads(data.strip())
        if parsed.get("type") == "control_request":
            self._pending_control_ids.append(parsed["request_id"])
            self._control_event.set()

    def read_messages(self) -> AsyncIterator[dict[str, Any]]:
        return self._read_impl()

    async def _read_impl(self) -> AsyncIterator[dict[str, Any]]:
        # Wait for and respond to the initialize control request
        await self._control_event.wait()
        self._control_event = anyio.Event()

        for req_id in self._pending_control_ids:
            yield {
                "type": "control_response",
                "response": {
                    "subtype": "success",
                    "request_id": req_id,
                    "response": {},
                },
            }
        self._pending_control_ids.clear()

        # Wait briefly for the user message write + end_input
        await anyio.sleep(0.01)

        for msg in self._messages:
            yield msg

    async def close(self) -> None:
        self._connected = False

    def is_ready(self) -> bool:
        return self._connected

    async def end_input(self) -> None:
        pass


def load_cassette(name: str) -> list[dict[str, Any]]:
    """Load a cassette file by name (without .json extension)."""
    path = CASSETTES_DIR / f"{name}.json"
    with path.open() as f:
        return json.load(f)
