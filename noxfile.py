import os

import nox

GSM8K_ENVIRONMENT_PACKAGE = (
    "gsm8k @ git+https://github.com/willccbb/verifiers.git"
    "@b4d851db42cebbab2358b827fd0ed19773631937"
    "#subdirectory=environments/gsm8k ; python_version >= '3.11'"
)
SUPPORTED_PYTHON_VERSIONS = ["3.10", "3.11", "3.12", "3.13"]
NUM_TRACE_SERVER_SHARDS = 4
VERIFIERS_MIN_PYTHON_VERSION = (3, 11)

nox.options.default_venv_backend = "uv"
nox.options.reuse_existing_virtualenvs = True
nox.options.stop_on_first_error = True


@nox.session
def lint(session: nox.Session):
    session.run("uv", "sync", "--active", "--group", "dev", "--frozen")

    dry_run = session.posargs and "dry-run" in session.posargs
    all_files = session.posargs and "--all-files" in session.posargs
    ruff_only = session.posargs and "--ruff-only" in session.posargs

    if ruff_only:
        # Run only ruff checks on all files
        session.run("prek", "run", "--hook-stage=pre-push", "ruff-check", "--all-files")
        session.run(
            "prek", "run", "--hook-stage=pre-push", "ruff-format", "--all-files"
        )
    elif dry_run:
        session.run(
            "prek",
            "run",
            "--hook-stage",
            "pre-push",
            "--files",
            "./weave/__init__.py",
        )
    elif all_files:
        # Allow running on all files if explicitly requested
        session.run("prek", "run", "--hook-stage=pre-push", "--all-files")
    else:
        # Default: run only on staged files for faster execution
        session.run("prek", "run", "--hook-stage=pre-push")


# Doctest coverage is opt-in per module via this allowlist rather than a
# repo-wide `pytest --doctest-modules` sweep. Most modules either have no
# doctests or carry illustrative `>>>` blocks that intentionally don't execute
# (they construct models, hit the network, or download weights). An explicit
# list keeps the run green and lets coverage grow deliberately, one reviewed
# module at a time. Every module listed here must pass `pytest
# --doctest-modules`; the `doctest` CI job enforces it.
DOCTEST_MODULES = [
    "weave/utils/project_id.py",
    "weave/utils/dict_utils.py",
    "weave/trace/view_utils.py",
    "weave/trace_server/call_stats_helpers.py",
    "weave/trace_server/clickhouse/utilities.py",
    "weave/trace_server/trace_server_common.py",
    "weave/trace_server/feedback_payload_schema.py",
    "weave/trace_server/orm.py",
]


@nox.session
def doctest(session: nox.Session):
    """Run doctests for the modules in the DOCTEST_MODULES allowlist.

    Pass file paths as posargs to run a subset, e.g.
        nox -e doctest -- weave/utils/dict_utils.py
    """
    session.run(
        "uv",
        "sync",
        "--active",
        "--group",
        "test",
        "--group",
        "trace_server",
        "--frozen",
    )
    targets = session.posargs or DOCTEST_MODULES
    # `-p no:ddtrace` mirrors the tests session: the ddtrace pytest plugin can
    # hang during initialization.
    session.run("pytest", "--doctest-modules", "-p", "no:ddtrace", *targets)


# Shards that don't have corresponding optional dependencies in pyproject.toml
# Note: _test/_tests shards are dependency groups, not optional dependencies
SHARDS_WITHOUT_EXTRAS = {
    "custom",
    "flow",
    "trace",
    "trace_calls_merged_only",
    "trace_no_server",
    "trace_server",
    "trace_server_bindings",
    "trace_server_migrator",
    "openai_realtime",
    "autogen_tests",
    "verifiers_test",
    "pandas_test",
    "scorers",
    # google_adk is installed post-sync (see tests()) rather than via an
    # extra: google-adk pins opentelemetry-sdk<=1.41.1, so locking it
    # universally would drag every shard's shared resolution down to that
    # ceiling. Keeping it out of the lock leaves the shared resolution alone.
    "google_adk",
}


@nox.session(python=SUPPORTED_PYTHON_VERSIONS)
@nox.parametrize(
    "shard",
    [
        # The `custom` shard is included if you want to run your own tests.  By default,
        # no tests are specified, which means ALL tests will run.  To run just your own
        # subset, you can pass `-- test_your_thing.py` to nox.
        # For example,
        #   nox -e "tests-3.12(shard='custom')" -- test_your_thing.py
        "custom",
        "flow",
        "trace_server",
        "trace_server_bindings",
        "trace_server_migrator",
        "anthropic",
        "cerebras",
        "cohere",
        "crewai",
        "dspy",
        "gepa",
        "google_genai",
        "google_adk",
        "groq",
        "instructor",
        "langchain_nvidia_ai_endpoints",
        "langchain",
        "litellm",
        "llamaindex",
        "mistral",
        "notdiamond",
        "openai",
        "openai_agents",
        "openai_realtime",
        "vertexai",
        "bedrock",
        "scorers",
        "pandas_test",
        "huggingface",
        "smolagents",
        "fastmcp",
        "verdict",
        "claude_agent_sdk",
        "verifiers_test",
        "autogen_tests",
        "trace",
        "trace_calls_merged_only",
        "trace_no_server",
        "stainless",
    ],
)
def tests(session: nox.Session, shard: str):
    # Normalize nox's configured Python string, like "3.10", for numeric comparison.
    python_version = tuple(int(part) for part in str(session.python).split(".")[:2])
    if shard == "verifiers_test" and python_version < VERIFIERS_MIN_PYTHON_VERSION:
        session.skip("verifiers_test requires Python >= 3.11")

    # Only add --extra shard if the shard has a corresponding optional dependency
    # Use --active to sync to the active nox virtual environment
    # Test-related shards (ending in _test/_tests) are dependency groups, not extras
    sync_args = ["uv", "sync", "--active", "--group", "test", "--frozen"]

    if shard not in SHARDS_WITHOUT_EXTRAS:
        sync_args.extend(["--extra", shard])
    elif shard in {"autogen_tests", "verifiers_test", "pandas_test"}:
        sync_args.extend(["--group", shard])
    elif shard in {"trace_server", "trace_server_migrator"}:
        # trace_server shards need both trace_server dependency group and trace_server_tests
        sync_args.extend(["--group", "trace_server", "--group", "trace_server_tests"])
    elif shard == "scorers":
        # scorer tests include a few that hit W&B Artifacts directly, so install
        # both extras to cover the full suite.
        sync_args.extend(["--extra", "scorers", "--extra", "wandb"])

    session.run(*sync_args)

    if shard == "openai_agents":
        # Keep the public extra broad for runtime compatibility, but exercise the
        # newer SDK span classes in CI.
        session.run("uv", "pip", "install", "--upgrade", "openai-agents>=0.14.7")

    if shard == "google_adk":
        # Installed here (not via an extra) so it stays out of the shared
        # uv.lock — google-adk pins opentelemetry-sdk<=1.41.1, which weave now
        # tolerates (the ADK integration vendors its GenAI semconv keys). This
        # downgrades otel in this env only; weave works on the older semconv.
        session.run("uv", "pip", "install", "google-adk>=2.2.0")

    env = {
        k: session.env.get(k) or os.getenv(k)
        for k in [
            "WEAVE_SENTRY_ENV",
            "CI",
            "WB_SERVER_HOST",
            "WF_CLICKHOUSE_HOST",
            "WEAVE_SERVER_DISABLE_ECOSYSTEM",
            "DD_TRACE_ENABLED",
        ]
    }
    # Add the GOOGLE_API_KEY environment variable for the "google" shard
    if shard == "google_genai":
        env["GOOGLE_API_KEY"] = os.getenv("GOOGLE_API_KEY", "MISSING")

    # Add the NVIDIA_API_KEY environment variable for the "langchain_nvidia_ai_endpoints" shard
    if shard == "langchain_nvidia_ai_endpoints":
        env["NVIDIA_API_KEY"] = os.getenv("NVIDIA_API_KEY", "MISSING")

    # we are doing some integration test in test_llm_integrations.py that requires
    # setting some environment variables for the LLM providers
    if shard == "scorers":
        env["GOOGLE_API_KEY"] = os.getenv("GOOGLE_API_KEY", "MISSING")
        env["GEMINI_API_KEY"] = os.getenv("GEMINI_API_KEY", "MISSING")
        env["ANTHROPIC_API_KEY"] = os.getenv("ANTHROPIC_API_KEY", "MISSING")
        env["MISTRAL_API_KEY"] = os.getenv("MISTRAL_API_KEY", "MISSING")
        env["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY", "MISSING")
        # A few scorer tests download tiny models from W&B Artifacts.
        env["WANDB_API_KEY"] = os.getenv("WANDB_API_KEY", "MISSING")

    if shard == "openai_agents":
        env["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY", "MISSING")

    default_test_dirs = [f"tests/integrations/{shard}/"]
    test_dirs_dict = {
        "custom": [],
        "flow": ["tests/flow/"],
        "trace_server": ["tests/trace_server/", "tests/shared/"],
        "trace_server_bindings": ["tests/trace_server_bindings/"],
        "trace_server_migrator": ["tests/trace_server_migrator/"],
        "stainless": ["tests/trace_server_bindings/"],
        "scorers": ["tests/scorers/"],
        "autogen_tests": ["tests/integrations/autogen/"],
        "verifiers_test": ["tests/integrations/verifiers/"],
        "trace": [
            "tests/trace/",
            "tests/compat/",
            "tests/utils/",
            "tests/wandb_interface/",
            "tests/session/",
        ],
        "trace_calls_merged_only": [
            "tests/trace/",
            "tests/compat/",
            "tests/utils/",
            "tests/wandb_interface/",
            "tests/session/",
        ],
        "trace_no_server": [
            "tests/trace/",
            "tests/durability/",
            "tests/utils/",
            "tests/compat/",
            "tests/wandb_interface/",
            "tests/session/",
        ],
    }

    test_dirs = test_dirs_dict.get(shard, default_test_dirs)

    for test_dir in test_dirs:
        if not os.path.exists(test_dir):
            raise ValueError(f"Test directory {test_dir} does not exist")

    # Each worker gets its own isolated database namespace
    # Only use parallel workers for the trace shard if we have more than 1 CPU core
    if shard in {"trace", "trace_calls_merged_only"}:
        cpu_count = os.cpu_count()
        if cpu_count is not None and cpu_count > 1:
            session.posargs.insert(0, f"-n{cpu_count}")

    # Add sharding logic for trace1, trace2, trace3
    pytest_args = [
        "pytest",
        "-p",
        "no:ddtrace",  # Disable ddtrace pytest plugin to prevent hangs during initialization
        "--durations=20",
        "--strict-markers",
        "--cov=weave",
        "--cov-report=html",
        "--cov-report=xml",
        "--cov-branch",
    ]

    if shard in {"trace", "trace_calls_merged_only"}:
        pytest_args.extend(["-m", "trace_server"])

    if shard == "trace_no_server":
        pytest_args.extend(["-m", "not trace_server"])

    if shard == "trace_calls_merged_only":
        env["WEAVE_USE_CALLS_COMPLETE"] = "false"

    # Set trace-server flag for stainless shard
    if shard == "stainless":
        pytest_args.extend(["--remote-http-trace-server=stainless"])

    if shard == "verifiers_test":
        # Pinning to this commit because the latest version of the gsm8k environment is broken.
        session.install(GSM8K_ENVIRONMENT_PACKAGE)

    # Check if posargs contains test files (ending with .py or containing :: for specific tests)
    has_test_files = any(
        arg.endswith(".py") or "::" in arg
        for arg in session.posargs
        if not arg.startswith("-")
    )

    # If specific test files are provided, don't add default test directories
    if has_test_files:
        session.run(
            *pytest_args,
            *session.posargs,
            env=env,
        )
    else:
        # Include default test directories when no specific files are provided
        session.run(
            *pytest_args,
            *session.posargs,
            *test_dirs,
            env=env,
        )
