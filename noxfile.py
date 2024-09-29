import nox

nox.options.default_venv_backend = "uv"

SUPPORTED_PYTHON_VERSIONS = ["3.9", "3.10", "3.11", "3.12"]


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
        "groq",
        "instructor",
        "langchain",
        "litellm",
        "llamaindex",
        "mistral0",
        "mistral1",
        "openai",
    ],
)
def tests(session, shard):
    session.install("-e", f".[{shard},test]")
    session.chdir("weave")

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

    if shard == "trace":
        test_dirs = ["tests/trace/", "trace/"]
    elif shard == "trace_server":
        test_dirs = ["trace_server/"]
    elif shard == "llamaindex":
        test_dirs = ["integrations/llamaindex/"]
        session.posargs.insert(0, "-n4")
    else:
        test_dirs = [f"integrations/{shard}/"]

    session.run("pytest", *session.posargs, *test_dirs, env=env)


# Configure pytest
# nox.options.sessions = ["tests", "lint", "integration_tests"]
nox.options.reuse_existing_virtualenvs = True
nox.options.stop_on_first_error = True
