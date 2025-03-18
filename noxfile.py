import nox

nox.options.default_venv_backend = "uv"

SUPPORTED_PYTHON_VERSIONS = ["3.9", "3.10", "3.11", "3.12", "3.13"]
PY313_INCOMPATIBLE_SHARDS = [
    "anthropic",
    "cohere",
    "dspy",
    "langchain",
    "langchain_nvidia_ai_endpoints",
    "litellm",
    "notdiamond",
    "google_ai_studio",
    "bedrock",
    "scorers",
]


@nox.session
def lint(session):
    session.install("pre-commit", "jupyter")
    session.run("pre-commit", "run", "--hook-stage=pre-push", "--all-files")


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
        "trace",
        "trace_server",
        "anthropic",
        "cerebras",
        "cohere",
        "dspy",
        "google_ai_studio",
        "groq",
        "instructor",
        "langchain_nvidia_ai_endpoints",
        "langchain",
        "litellm",
        "llamaindex",
        "mistral0",
        "mistral1",
        "notdiamond",
        "openai",
        "openai_agents",
        "vertexai",
        "bedrock",
        "scorers",
        "pandas-test",
        "huggingface",
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
            "DD_TRACE_ENABLED",
        ]
    }
    # Add the GOOGLE_API_KEY environment variable for the "google" shard
    if shard == "google_ai_studio":
        env["GOOGLE_API_KEY"] = session.env.get("GOOGLE_API_KEY")

    # Add the NVIDIA_API_KEY environment variable for the "langchain_nvidia_ai_endpoints" shard
    if shard == "langchain_nvidia_ai_endpoints":
        env["NVIDIA_API_KEY"] = session.env.get("NVIDIA_API_KEY")

    # we are doing some integration test in test_llm_integrations.py that requires
    # setting some environment variables for the LLM providers
    if shard == "scorers":
        env["GOOGLE_API_KEY"] = session.env.get("GOOGLE_API_KEY")
        env["GEMINI_API_KEY"] = session.env.get("GEMINI_API_KEY")
        env["ANTHROPIC_API_KEY"] = session.env.get("ANTHROPIC_API_KEY")
        env["MISTRAL_API_KEY"] = session.env.get("MISTRAL_API_KEY")
        env["OPENAI_API_KEY"] = session.env.get("OPENAI_API_KEY")

    if shard == "openai_agents":
        env["OPENAI_API_KEY"] = session.env.get("OPENAI_API_KEY")

    default_test_dirs = [f"integrations/{shard}/"]
    test_dirs_dict = {
        "custom": [],
        "trace": ["trace/"],
        "trace_server": ["trace_server/"],
        "mistral0": ["integrations/mistral/v0/"],
        "mistral1": ["integrations/mistral/v1/"],
        "scorers": ["scorers/"],
    }

    test_dirs = test_dirs_dict.get(shard, default_test_dirs)

    # seems to resolve ci issues
    if shard == "llamaindex":
        session.posargs.insert(0, "-n4")

    session.run(
        "pytest",
        "--strict-markers",
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
