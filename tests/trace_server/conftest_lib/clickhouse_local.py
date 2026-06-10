"""pytest plugin: auto-started local ClickHouse server (no docker).

PYTEST_DONT_REWRITE — this module is imported by conftest_lib.clickhouse_server
before pytest registers it as a plugin; without this marker every run emits a
"module already imported" assertion-rewrite warning. There are no test asserts
here, so rewriting has nothing to do anyway.

Selected with ``--trace-server=clickhouse-local`` (or the ``--clickhouse-local``
shorthand). One real ``clickhouse server`` subprocess is started per pytest
invocation, owned by the xdist controller (or the lone process when xdist is
not in play), and torn down at unconfigure. Workers receive the server address
via ``workerinput`` and share the server exactly like the dockerized CI setup
does today (per-worker database suffixes provide isolation).

At configure time the ``--trace-server`` option is normalized to plain
``"clickhouse"`` so every downstream consumer (fixtures, marker logic, skips)
behaves byte-identically to a dockerized/external ClickHouse run. The only
observable difference is who provisions the server.

The server runs from a throwaway directory (on Linux, ``/dev/shm`` when it has
room, so the data dir is backed by RAM) with a minimal config that mirrors the
parts of the CI docker setup tests rely on:

- default user, empty password, ``access_management`` enabled
  (``CLICKHOUSE_DEFAULT_ACCESS_MANAGEMENT=1`` in CI docker runs),
- ``test_overrides.xml`` merged into ``users.d/`` (single source of truth —
  the file is copied verbatim, and startup asserts the merge actually took),
- UTC server timezone (the docker image default; dev machines may not be UTC),
- system log tables (query_log & co.) are simply not configured — nothing in
  weave or its tests reads them, and skipping them avoids background flush
  work the docker image pays for.
"""

from __future__ import annotations

import atexit
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx
import pytest

try:
    import resource
except ImportError:  # Windows: no resource module; this backend is POSIX-only.
    resource = None  # type: ignore[assignment]

# Flag value for --trace-server selecting this backend.
CLICKHOUSE_LOCAL_FLAG = "clickhouse-local"

# Explicit path to the server binary; takes precedence over PATH lookup.
BINARY_ENV_VAR = "WEAVE_CLICKHOUSE_BINARY"
# Names probed on PATH, in order. "clickhouse" is the multi-tool binary
# (invoked as `clickhouse server`), "clickhouse-server" the standalone one.
BINARY_PATH_NAMES = ("clickhouse", "clickhouse-server")
# Where to point users when no binary can be found.
BINARY_INSTALL_HINT = "bin/get_clickhouse.sh"

# Root directory override for the server's scratch space.
DATA_ROOT_ENV_VAR = "WEAVE_CLICKHOUSE_LOCAL_DATA_ROOT"
# RAM-backed tmpfs used when available (Linux CI runners).
SHM_DIR = Path("/dev/shm")
# Don't use /dev/shm unless it has this much headroom; test data is small but
# running out of shm mid-session fails confusingly.
SHM_MIN_FREE_BYTES = 4 * 1024**3

# Server-side profile defaults applied to test servers; copied into users.d/.
TEST_OVERRIDES_XML = Path(__file__).parent / "test_overrides.xml"

# Seconds to wait for /ping after spawning the server.
STARTUP_TIMEOUT_SECONDS = 30.0
# Seconds between health probes while waiting for startup.
STARTUP_POLL_INTERVAL_SECONDS = 0.05
# Fresh-port retries when the server fails to come up (port TOCTOU race).
MAX_START_ATTEMPTS = 3
# Seconds to wait for graceful shutdown before SIGKILL.
SHUTDOWN_TIMEOUT_SECONDS = 10.0
# Mirrors the `--ulimit nofile=262144:262144` the docker runs use.
TARGET_NOFILE_LIMIT = 262144
# Log lines surfaced in error messages when startup fails.
LOG_TAIL_LINES = 40

# Keys injected into xdist workerinput / pytest stash.
WORKERINPUT_ADDRESS_KEY = "weave_clickhouse_local_address"
server_stash_key = pytest.StashKey["ClickHouseLocalServer"]()
address_stash_key = pytest.StashKey[tuple[str, int]]()

# The server only ever listens on loopback. 127.0.0.1 (not "localhost") so a
# resolver that prefers ::1 can't route clients past the listen address.
LISTEN_HOST = "127.0.0.1"

CONFIG_XML_TEMPLATE = """\
<clickhouse>
    <logger>
        <level>warning</level>
        <log>{root}/log/clickhouse-server.log</log>
        <errorlog>{root}/log/clickhouse-server.err.log</errorlog>
        <console>0</console>
    </logger>
    <listen_host>{listen_host}</listen_host>
    <http_port>{http_port}</http_port>
    <tcp_port>{tcp_port}</tcp_port>
    <path>{root}/data/</path>
    <tmp_path>{root}/data/tmp/</tmp_path>
    <user_files_path>{root}/data/user_files/</user_files_path>
    <format_schema_path>{root}/data/format_schemas/</format_schema_path>
    <user_directories>
        <users_xml>
            <path>{root}/etc/users.xml</path>
        </users_xml>
        <local_directory>
            <path>{root}/data/access/</path>
        </local_directory>
    </user_directories>
    <!-- Docker image default; dev machines may run in any timezone. -->
    <timezone>UTC</timezone>
    <!-- Test datasets are tiny; don't reserve the production-sized default
         caches, and leave RAM for pytest workers on shared CI runners. -->
    <mark_cache_size>268435456</mark_cache_size>
    <max_server_memory_usage_to_ram_ratio>0.5</max_server_memory_usage_to_ram_ratio>
</clickhouse>
"""

USERS_XML_TEMPLATE = """\
<clickhouse>
    <profiles>
        <default>
{profile_overrides}
        </default>
    </profiles>
    <users>
        <default>
            <password></password>
            <networks>
                <ip>127.0.0.1</ip>
                <ip>::1</ip>
            </networks>
            <profile>default</profile>
            <quota>default</quota>
            <access_management>1</access_management>
        </default>
    </users>
    <quotas>
        <default></default>
    </quotas>
</clickhouse>
"""

# JIT compilation (all three paths) crashes at runtime on official macOS
# builds — symbol resolution fails with CANNOT_COMPILE_CODE
# (e.g. _memcmpSmallCharsAllowOverflow15), and compile_sort_description is the
# sneaky third path that triggers only after the same sort runs 3 times.
# Linux builds keep JIT ON for parity with the docker image: the heavy xdist
# shards repeat the same aggregation/sort shapes thousands of times, and
# disabling JIT there measured ~15% slower (CI trace_calls_complete_only:
# 319-344s without JIT vs 276-297s dockerized with JIT, same job).
MACOS_PROFILE_OVERRIDES = """\
            <compile_expressions>0</compile_expressions>
            <compile_aggregate_expressions>0</compile_aggregate_expressions>
            <compile_sort_description>0</compile_sort_description>"""


def _users_xml() -> str:
    overrides = MACOS_PROFILE_OVERRIDES if sys.platform == "darwin" else ""
    return USERS_XML_TEMPLATE.format(profile_overrides=overrides)


def is_clickhouse_local_requested(config: pytest.Config) -> bool:
    """True when this run was invoked with the clickhouse-local backend.

    Reads the *raw* options, so only meaningful before `pytest_configure`
    normalizes --trace-server; afterwards consult the stash instead.
    """
    return config.getoption(
        "--trace-server", default=None
    ) == CLICKHOUSE_LOCAL_FLAG or config.getoption("--clickhouse-local", default=False)


def get_clickhouse_local_address(config: pytest.Config) -> tuple[str, int] | None:
    """(host, port) of the session's local server, or None when not active."""
    return config.stash.get(address_stash_key, None)


def _resolve_binary() -> str:
    explicit = os.environ.get(BINARY_ENV_VAR)
    if explicit:
        if not Path(explicit).exists():
            raise pytest.UsageError(f"{BINARY_ENV_VAR}={explicit} does not exist")
        return explicit
    for name in BINARY_PATH_NAMES:
        found = shutil.which(name)
        if found:
            return found
    raise pytest.UsageError(
        "--trace-server=clickhouse-local needs a ClickHouse server binary. "
        f"Set {BINARY_ENV_VAR}, put `clickhouse` on PATH, or run "
        f"{BINARY_INSTALL_HINT} (macOS: `brew install --cask clickhouse`)."
    )


def _server_command(binary: str) -> list[str]:
    # The multi-tool `clickhouse` binary needs the `server` subcommand; the
    # standalone `clickhouse-server` binary must not get one.
    if Path(binary).name == "clickhouse-server":
        return [binary]
    return [binary, "server"]


def _data_root_base() -> Path:
    override = os.environ.get(DATA_ROOT_ENV_VAR)
    if override:
        return Path(override)
    if sys.platform == "linux" and SHM_DIR.is_dir() and os.access(SHM_DIR, os.W_OK):
        if shutil.disk_usage(SHM_DIR).free >= SHM_MIN_FREE_BYTES:
            return SHM_DIR
    return Path(tempfile.gettempdir())


def _find_free_port() -> int:
    with socket.socket() as sock:
        sock.bind((LISTEN_HOST, 0))
        return sock.getsockname()[1]


def _child_preexec() -> None:
    # New process group so teardown can kill the server and any helpers it
    # forks in one signal, mirroring the docker-run cleanup semantics.
    os.setsid()
    if resource is None:
        return
    # Mirrors the docker runs' `--ulimit nofile=262144:262144`.
    try:
        _soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        target = hard if hard != resource.RLIM_INFINITY else TARGET_NOFILE_LIMIT
        resource.setrlimit(
            resource.RLIMIT_NOFILE, (min(TARGET_NOFILE_LIMIT, target), hard)
        )
    except (ValueError, OSError):
        pass


@dataclass
class ClickHouseLocalServer:
    """A locally spawned `clickhouse server` process and its scratch dir."""

    process: subprocess.Popen
    host: str
    http_port: int
    root_dir: Path
    _stopped: bool = field(default=False, init=False)

    @classmethod
    def start(cls) -> ClickHouseLocalServer:
        if sys.platform == "win32":
            raise pytest.UsageError(
                "clickhouse-local backend is not supported on Windows "
                "(no native ClickHouse server)."
            )
        binary = _resolve_binary()
        last_error = ""
        for _attempt in range(MAX_START_ATTEMPTS):
            server, error = cls._start_once(binary)
            if server is not None:
                return server
            last_error = error
        raise pytest.UsageError(
            f"clickhouse-local server failed to start after "
            f"{MAX_START_ATTEMPTS} attempts:\n{last_error}"
        )

    @classmethod
    def _start_once(cls, binary: str) -> tuple[ClickHouseLocalServer | None, str]:
        """One launch attempt. Returns (server, "") or (None, error_detail)."""
        root = Path(tempfile.mkdtemp(prefix="weave-chlocal-", dir=_data_root_base()))
        http_port = _find_free_port()
        tcp_port = _find_free_port()

        etc_dir = root / "etc"
        users_d = etc_dir / "users.d"
        log_dir = root / "log"
        for directory in (etc_dir, users_d, log_dir):
            directory.mkdir(parents=True)

        config_path = etc_dir / "config.xml"
        config_path.write_text(
            CONFIG_XML_TEMPLATE.format(
                root=root,
                listen_host=LISTEN_HOST,
                http_port=http_port,
                tcp_port=tcp_port,
            )
        )
        (etc_dir / "users.xml").write_text(_users_xml())
        # Verbatim copy: keeps test_overrides.xml the single source of truth
        # for server-side test settings across docker and local runs.
        shutil.copyfile(TEST_OVERRIDES_XML, users_d / TEST_OVERRIDES_XML.name)

        startup_log = log_dir / "startup.log"
        with startup_log.open("wb") as startup_out:
            process = subprocess.Popen(
                [*_server_command(binary), f"--config-file={config_path}"],
                stdout=startup_out,
                stderr=subprocess.STDOUT,
                cwd=root,
                preexec_fn=_child_preexec,  # noqa: PLW1509
            )

        server = cls(
            process=process, host=LISTEN_HOST, http_port=http_port, root_dir=root
        )
        # Safety net for exits that skip pytest_unconfigure (crashes,
        # os._exit). stop() is idempotent, so the normal path is unaffected.
        atexit.register(server.stop, silent=True)
        try:
            server._wait_until_healthy()
            server._assert_test_overrides_applied()
        except Exception as e:
            detail = f"{e}\n{server._log_tail()}"
            server.stop(silent=True)
            return None, detail
        return server, ""

    def _wait_until_healthy(self) -> None:
        deadline = time.monotonic() + STARTUP_TIMEOUT_SECONDS
        url = f"http://{self.host}:{self.http_port}/ping"
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise RuntimeError(
                    f"clickhouse server exited with code {self.process.returncode} "
                    "during startup"
                )
            try:
                if httpx.get(url, timeout=1.0).status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            time.sleep(STARTUP_POLL_INTERVAL_SECONDS)
        raise TimeoutError(
            f"clickhouse server not healthy at {url} after {STARTUP_TIMEOUT_SECONDS}s"
        )

    def _query(self, query: str) -> str:
        response = httpx.get(
            f"http://{self.host}:{self.http_port}/",
            params={"query": query},
            timeout=5.0,
        )
        response.raise_for_status()
        return response.text.strip()

    def _assert_test_overrides_applied(self) -> None:
        # Canary: async_insert=0 only holds if users.d/test_overrides.xml was
        # merged into the default profile. The file is copied verbatim, so one
        # setting proves the whole file landed.
        value = self._query(
            "SELECT value FROM system.settings WHERE name = 'async_insert'"
        )
        if value != "0":
            raise RuntimeError(
                "test_overrides.xml was not applied to the local clickhouse "
                f"server (async_insert={value!r}, expected '0')"
            )

    def _log_tail(self) -> str:
        chunks = []
        for name in ("startup.log", "clickhouse-server.err.log"):
            path = self.root_dir / "log" / name
            if path.exists():
                lines = path.read_text(errors="replace").splitlines()
                tail = "\n".join(lines[-LOG_TAIL_LINES:])
                chunks.append(f"--- {name} (last {LOG_TAIL_LINES} lines) ---\n{tail}")
        return "\n".join(chunks)

    def stop(self, silent: bool = False) -> None:
        if self._stopped:
            return
        self._stopped = True
        exited_early = self.process.poll() is not None
        if exited_early and not silent:
            print(
                "clickhouse-local server exited before teardown "
                f"(code {self.process.returncode}):\n{self._log_tail()}",
                file=sys.stderr,
            )
        try:
            # SIGKILL, not SIGTERM: the data dir is throwaway, so there is
            # nothing for a graceful shutdown (merge/mutation draining, log
            # flushing) to protect — it only adds seconds to every session.
            os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
            self.process.wait(timeout=SHUTDOWN_TIMEOUT_SECONDS)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            pass
        finally:
            shutil.rmtree(self.root_dir, ignore_errors=True)


def _validate_flag_combination(config: pytest.Config) -> None:
    if config.getoption("--sqlite", default=False) or (
        config.getoption("--trace-server", default=None) == "sqlite"
    ):
        raise pytest.UsageError(
            "clickhouse-local conflicts with sqlite backend selection; pick one backend"
        )


def pytest_configure(config: pytest.Config) -> None:
    if not is_clickhouse_local_requested(config):
        return
    _validate_flag_combination(config)

    # Normalize the semantic backend to plain "clickhouse" so every
    # downstream getoption("--trace-server") read behaves identically to a
    # dockerized/external ClickHouse run. Provisioning is recorded in the
    # stash, not the flag.
    config.option.trace_server = "clickhouse"

    # xdist sets workerinput on worker processes (same pattern as
    # _get_worker_db_suffix in tests/trace_server/conftest.py).
    workerinput = getattr(config, "workerinput", None)
    if workerinput is not None:
        address = workerinput.get(WORKERINPUT_ADDRESS_KEY)
        if address is None:
            raise pytest.UsageError(
                "xdist worker started in clickhouse-local mode but the "
                "controller did not provide a server address"
            )
        host, port = address[0], int(address[1])
    else:
        if config.option.collectonly:
            return
        server = ClickHouseLocalServer.start()
        config.stash[server_stash_key] = server
        host, port = server.host, server.http_port

    # Everything (fixtures, ClickHouseTraceServer.from_env, subprocesses)
    # resolves the server through these env vars.
    os.environ["WF_CLICKHOUSE_HOST"] = host
    os.environ["WF_CLICKHOUSE_PORT"] = str(port)
    config.stash[address_stash_key] = (host, port)


@pytest.hookimpl(optionalhook=True)
def pytest_configure_node(node) -> None:
    """Controller-side xdist hook: hand the server address to each worker."""
    server = node.config.stash.get(server_stash_key, None)
    if server is not None:
        node.workerinput[WORKERINPUT_ADDRESS_KEY] = [
            server.host,
            str(server.http_port),
        ]


def pytest_unconfigure(config: pytest.Config) -> None:
    server = config.stash.get(server_stash_key, None)
    if server is not None:
        server.stop()
