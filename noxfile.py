import nox

nox.options.default_venv_backend = "uv"

SUPPORTED_PYTHON_VERSIONS = ["3.9", "3.10", "3.11", "3.12"]


@nox.session
def lint(session):
    session.install("-r", "requirements.test.txt")
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
    session.install("-e", f".[{shard}]")
    session.install("-r", "requirements.test.txt")
    session.chdir("weave")

    # Set environment variables
    env = {
        "WEAVE_SENTRY_ENV": session.env.get("WEAVE_SENTRY_ENV"),
        "CI": session.env.get("CI"),
        "WB_SERVER_HOST": session.env.get("WB_SERVER_HOST"),
        "WF_CLICKHOUSE_HOST": session.env.get("WF_CLICKHOUSE_HOST"),
        "WEAVE_SERVER_DISABLE_ECOSYSTEM": session.env.get(
            "WEAVE_SERVER_DISABLE_ECOSYSTEM"
        ),
    }

    # Run tests
    if shard == "trace":
        session.run("pytest", *session.posargs, "tests/trace/", "trace/", env=env)
    elif shard == "trace_server":
        session.run("pytest", *session.posargs, "trace_server/", env=env)
    elif shard == "llamaindex":
        session.run(
            "pytest", "-n4", *session.posargs, "integrations/llamaindex/", env=env
        )
    else:
        session.run("pytest", *session.posargs, f"integrations/{shard}/", env=env)


# Configure pytest
# nox.options.sessions = ["tests", "lint", "integration_tests"]
nox.options.reuse_existing_virtualenvs = True
nox.options.stop_on_first_error = True
