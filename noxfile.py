import nox

nox.options.default_venv_backend = "uv"

SUPPORTED_PYTHON_VERSIONS = ["3.9", "3.10", "3.11", "3.12", "3.13"]
PY313_INCOMPATIBLE_SHARDS = [
    "anthropic",
    "cohere",
    "dspy",
    "langchain",
    "litellm",
    "notdiamond",
    "google_ai_studio",
    "scorers_tests",
]


@nox.session
def lint(session):
    session.install("pre-commit", "jupyter")
    session.run("pre-commit", "run", "--hook-stage=pre-push", "--all-files")


@nox.session(python=SUPPORTED_PYTHON_VERSIONS)
@nox.parametrize(
    "shard",
    [
        "trace",
        "trace_server",
        "anthropic",
        "cerebras",
        "cohere",
        "dspy",
        "google_ai_studio",
        "groq",
        "instructor",
        "langchain",
        "litellm",
        "llamaindex",
        "mistral0",
        "mistral1",
        "notdiamond",
        "openai",
        "scorers_tests",
        "pandas-test",
    ],
)
def tests(session, shard):
    if session.python.startswith("3.13") and shard in PY313_INCOMPATIBLE_SHARDS:
        session.skip(f"Skipping {shard=} as it is not compatible with Python 3.13")

    session.install("-e", f".[{shard},test]")
    session.chdir("tests")

    env = {
        k: session.env.get(k)
        for k in [
            "WEAVE_SENTRY_ENV",
            "CI",
            "WB_SERVER_HOST",
            "WF_CLICKHOUSE_HOST",
            "WEAVE_SERVER_DISABLE_ECOSYSTEM",
        ]
    }
    # Add the GOOGLE_API_KEY environment variable for the "google" shard
    if shard == "google_ai_studio":
        env["GOOGLE_API_KEY"] = session.env.get("GOOGLE_API_KEY")

    # we are doing some integration test in test_llm_integrations.py that requires
    # setting some environment variables for the LLM providers
    if shard == "scorers_tests":
        env["GOOGLE_API_KEY"] = session.env.get("GOOGLE_API_KEY")
        env["ANTHROPIC_API_KEY"] = session.env.get("ANTHROPIC_API_KEY")
        env["MISTRAL_API_KEY"] = session.env.get("MISTRAL_API_KEY")
        env["OPENAI_API_KEY"] = session.env.get("OPENAI_API_KEY")

    default_test_dirs = [f"integrations/{shard}/"]
    test_dirs_dict = {
        "trace": ["trace/"],
        "trace_server": ["trace_server/"],
        "mistral0": ["integrations/mistral/v0/"],
        "mistral1": ["integrations/mistral/v1/"],
        "scorers_tests": ["scorers/"],
    }

    test_dirs = test_dirs_dict.get(shard, default_test_dirs)

    # seems to resolve ci issues
    if shard == "llamaindex":
        session.posargs.insert(0, "-n4")

    session.run(
        "pytest",
        "--cov=weave",
        "--cov-report=html",
        "--cov-branch",
        *session.posargs,
        *test_dirs,
        env=env,
    )


# Configure pytest
nox.options.reuse_existing_virtualenvs = True
nox.options.stop_on_first_error = True
