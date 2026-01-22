import os

import nox

nox.options.default_venv_backend = "uv"
nox.options.reuse_existing_virtualenvs = True
nox.options.stop_on_first_error = True


SUPPORTED_PYTHON_VERSIONS = ["3.10", "3.11", "3.12", "3.13"]
INCOMPATIBLE_SHARDS = {
    "3.10": [
        "notdiamond",
        "verifiers_test",
    ],
    "3.13": [
        "cohere",
        "notdiamond",
        "verifiers_test",
    ],
}
NUM_TRACE_SERVER_SHARDS = 4


@nox.session
def lint(session: nox.Session):
    session.run("uv", "sync", "--active", "--group", "dev", "--frozen")

    dry_run = session.posargs and "dry-run" in session.posargs
    all_files = session.posargs and "--all-files" in session.posargs
    ruff_only = session.posargs and "--ruff-only" in session.posargs

    if ruff_only:
        # Run only ruff checks on all files
        session.run(
            "pre-commit", "run", "--hook-stage=pre-push", "ruff-check", "--all-files"
        )
        session.run(
            "pre-commit", "run", "--hook-stage=pre-push", "ruff-format", "--all-files"
        )
    elif dry_run:
        session.run(
            "pre-commit",
            "run",
            "--hook-stage",
            "pre-push",
            "--files",
            "./weave/__init__.py",
        )
    elif all_files:
        # Allow running on all files if explicitly requested
        session.run("pre-commit", "run", "--hook-stage=pre-push", "--all-files")
    else:
        # Default: run only on staged files for faster execution
        session.run("pre-commit", "run", "--hook-stage=pre-push")


# Shards that don't have corresponding optional dependencies in pyproject.toml
# Note: _test/_tests shards are dependency groups, not optional dependencies
SHARDS_WITHOUT_EXTRAS = {
    "custom",
    "flow",
    "trace",
    "trace_calls_complete_only",
    "trace_no_server",
    "trace_server",
    "trace_server_bindings",
    "openai_realtime",
    "autogen_tests",
    "verifiers_test",
    "pandas_test",
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
        "anthropic",
        "cerebras",
        "cohere",
        "crewai",
        "dspy",
        "google_genai",
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
        "mcp",
        "verdict",
        "verifiers_test",
        "autogen_tests",
        "trace",
        "trace_calls_complete_only",
        "trace_no_server",
        "stainless",
    ],
)
def tests(session: nox.Session, shard: str):
    python_version = session.python[:4]  # e.g., "3.10"
    if shard in INCOMPATIBLE_SHARDS.get(python_version, []):
        session.skip(
            f"Skipping {shard=} as it is not compatible with Python {python_version}"
        )
        return

    # Only add --extra shard if the shard has a corresponding optional dependency
    # Use --active to sync to the active nox virtual environment
    # Test-related shards (ending in _test/_tests) are dependency groups, not extras
    sync_args = ["uv", "sync", "--active", "--group", "test", "--frozen"]

    if shard not in SHARDS_WITHOUT_EXTRAS:
        sync_args.extend(["--extra", shard])
    elif shard in ("autogen_tests", "verifiers_test", "pandas_test"):
        sync_args.extend(["--group", shard])
    elif shard == "trace_server":
        # trace_server shard needs both trace_server dependency group and trace_server_tests
        sync_args.extend(["--group", "trace_server", "--group", "trace_server_tests"])

    session.run(*sync_args)

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

    if shard == "openai_agents":
        env["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY", "MISSING")

    default_test_dirs = [f"tests/integrations/{shard}/"]
    test_dirs_dict = {
        "custom": [],
        "flow": ["tests/flow/"],
        "trace_server": ["tests/trace_server/"],
        "trace_server_bindings": ["tests/trace_server_bindings/"],
        "stainless": ["tests/trace_server_bindings/"],
        "scorers": ["tests/scorers/"],
        "autogen_tests": ["tests/integrations/autogen/"],
        "verifiers_test": ["tests/integrations/verifiers/"],
        "trace": [
            "tests/trace/",
            "tests/compat/",
            "tests/utils/",
            "tests/wandb_interface/",
        ],
        "trace_calls_complete_only": [
            "tests/trace/",
            "tests/compat/",
            "tests/utils/",
            "tests/wandb_interface/",
        ],
        "trace_no_server": ["tests/trace/"],
    }

    test_dirs = test_dirs_dict.get(shard, default_test_dirs)

    for test_dir in test_dirs:
        if not os.path.exists(test_dir):
            raise ValueError(f"Test directory {test_dir} does not exist")

    # Each worker gets its own isolated database namespace
    # Only use parallel workers for the trace shard if we have more than 1 CPU core
    if shard in ("trace", "trace_calls_complete_only"):
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

    if shard in ("trace", "trace_calls_complete_only"):
        pytest_args.extend(["-m", "trace_server"])

    if shard == "trace_no_server":
        pytest_args.extend(["-m", "not trace_server"])

    if shard == "trace_calls_complete_only":
        env["WEAVE_USE_CALLS_COMPLETE"] = "true"

    # Set trace-server flag for stainless shard
    if shard == "stainless":
        pytest_args.extend(["--remote-http-trace-server=stainless"])

    if shard == "verifiers_test":
        # Pinning to this commit because the latest version of the gsm8k environment is broken.
        session.install(
            "git+https://github.com/willccbb/verifiers.git@b4d851db42cebbab2358b827fd0ed19773631937#subdirectory=environments/gsm8k"
        )

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
