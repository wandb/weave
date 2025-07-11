import os

import nox

nox.options.default_venv_backend = "uv"
nox.options.reuse_existing_virtualenvs = True
nox.options.stop_on_first_error = True


SUPPORTED_PYTHON_VERSIONS = ["3.9", "3.10", "3.11", "3.12", "3.13"]
PY313_INCOMPATIBLE_SHARDS = [
    "anthropic",
    "cohere",
    "dspy",
    "notdiamond",
    "crewai",
]
PY39_INCOMPATIBLE_SHARDS = [
    "crewai",
    "google_genai",
    "mcp",
    "smolagents",
    "dspy",
    "autogen_tests",
]
NUM_TRACE_SERVER_SHARDS = 4
INTEGRATION_SHARDS = [
    "anthropic",
    "cerebras",
    "cohere",
    "crewai",
    "dspy",
    "google_ai_studio",
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
    "vertexai",
    "bedrock",
    "scorers",
    "huggingface",
    "smolagents",
    "mcp",
    "verdict",
    "autogen_tests",
]


def get_default_pytest_args(*args):
    return [
        "pytest",
        "--durations=20",
        "--strict-markers",
        "--cov=weave",
        "--cov-report=html",
        "--cov-branch",
        *args,
    ]


def run_uv_sync_command_with_args(*args, session):
    session.run_install(
        "uv",
        "sync",
        *args,
        # The following is required to make nox use the virtualenv we created
        # https://nox.thea.codes/en/stable/cookbook.html#using-a-lockfile
        f"--python={session.virtualenv.location}",
        env={"UV_PROJECT_ENVIRONMENT": session.virtualenv.location},
    )


@nox.session
def lint(session):
    session.install("pre-commit", "jupyter")
    dry_run = session.posargs and "dry-run" in session.posargs
    if dry_run:
        session.run(
            "pre-commit",
            "run",
            "--hook-stage",
            "pre-push",
            "--files",
            "./weave/__init__.py",
        )
    else:
        session.run("pre-commit", "run", "--hook-stage=pre-push", "--all-files")


trace_server_shards = [f"trace{i}" for i in range(1, NUM_TRACE_SERVER_SHARDS + 1)]


@nox.session(python=SUPPORTED_PYTHON_VERSIONS)
def non_server_tests(session):
    run_uv_sync_command_with_args(
        "--group=test",
        session=session,
    )
    session.chdir("tests")

    pytest_args = get_default_pytest_args()
    if not (posargs := session.posargs):
        posargs = ["-m", "not trace_server"]
    test_dirs = ["trace/"]
    session.run(
        *pytest_args,
        *posargs,
        *test_dirs,
    )


@nox.session(python=SUPPORTED_PYTHON_VERSIONS)
@nox.parametrize(
    "shard",
    [
        "flow",
        "trace_server",
        "trace_server_bindings",
        "pandas-test",
        "trace",
        *INTEGRATION_SHARDS,
        *trace_server_shards,
    ],
)
def tests(session, shard):
    if session.python.startswith("3.13") and shard in PY313_INCOMPATIBLE_SHARDS:
        session.skip(f"Skipping {shard=} as it is not compatible with Python 3.13")

    if session.python.startswith("3.9") and shard in PY39_INCOMPATIBLE_SHARDS:
        session.skip(f"Skipping {shard=} as it is not compatible with Python 3.9")

    if shard in INTEGRATION_SHARDS:
        session.run_install(
            "uv",
            "sync",
            f"--extra={shard}",
            "--group=test",
            f"--python={session.virtualenv.location}",
            env={"UV_PROJECT_ENVIRONMENT": session.virtualenv.location},
        )
    else:
        session.run_install(
            "uv",
            "sync",
            "--group=test",
            f"--python={session.virtualenv.location}",
            env={"UV_PROJECT_ENVIRONMENT": session.virtualenv.location},
        )

    session.chdir("tests")

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
    if shard in ["google_ai_studio", "google_genai"]:
        env["GOOGLE_API_KEY"] = session.env.get("GOOGLE_API_KEY")

    if shard == "google_ai_studio":
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

    default_test_dirs = [f"integrations/{shard}/"]
    test_dirs_dict = {
        "custom": [],
        "flow": ["flow/"],
        "trace_server": ["trace_server/"],
        "trace_server_bindings": ["trace_server_bindings"],
        "mistral": ["integrations/mistral/"],
        "scorers": ["scorers/"],
        "autogen_tests": ["integrations/autogen/"],
        "trace": ["trace/"],
        **{shard: ["trace/"] for shard in trace_server_shards},
    }

    test_dirs = test_dirs_dict.get(shard, default_test_dirs)

    # seems to resolve ci issues
    if shard == "llamaindex":
        session.posargs.insert(0, "-n4")

    pytest_args = get_default_pytest_args()
    if shard in trace_server_shards:
        shard_id = int(shard[-1]) - 1
        pytest_args.extend(
            [
                f"--shard-id={shard_id}",
                f"--num-shards={NUM_TRACE_SERVER_SHARDS}",
                "-m trace_server",
            ]
        )

    session.run(
        *pytest_args,
        *session.posargs,
        *test_dirs,
        env=env,
    )
