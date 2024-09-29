import nox

nox.options.default_venv_backend = "uv"

@nox.session(python=["3.9", "3.10", "3.11", "3.12"])
def tests(session):
    session.install("-r", "requirements.test.txt")
    session.chdir("weave")
    session.run("pytest", *session.posargs)

@nox.session
def lint(session):
    session.install("-r", "requirements.test.txt")
    session.install("pre-commit", "jupyter")
    session.run("pre-commit", "run", "--hook-stage=pre-push", "--all-files")

@nox.session(python=["3.9", "3.10", "3.11", "3.12"])
@nox.parametrize("integration", [
    "trace", "trace_server", "anthropic", "cerebras", "cohere", "dspy",
    "groq", "instructor", "langchain", "litellm", "llamaindex",
    "mistral0", "mistral1", "openai"
])
def integration_tests(session, integration):
    session.install("-r", "requirements.test.txt")
    
    # Install integration-specific dependencies
    if integration == "anthropic":
        session.install("anthropic>=0.18.0")
    elif integration == "cerebras":
        session.install("cerebras-cloud-sdk")
    elif integration == "cohere":
        session.install("cohere>=5.9.1,<5.9.3")
    elif integration == "dspy":
        session.install("dspy>=0.1.5")
    elif integration == "groq":
        session.install("groq>=0.9.0")
    elif integration == "instructor":
        session.install("instructor>=1.4.3")
    elif integration == "langchain":
        session.install("langchain-core>=0.2.1", "langchain-openai>=0.1.7",
                        "langchain-community>=0.2.1", "chromadb>=0.5.0", "pysqlite3")
    elif integration == "litellm":
        session.install("litellm>=1.36.1", "semver")
    elif integration == "llamaindex":
        session.install("llama-index>=0.10.35")
    elif integration == "mistral0":
        session.install("mistralai>=0.1.8,<1.0.0")
    elif integration == "mistral1":
        session.install("mistralai>=1.0.0")
    elif integration == "openai":
        session.install("openai>=1.0.0")
    
    session.chdir("weave")
    
    # Set environment variables
    env = {
        "WEAVE_SENTRY_ENV": session.env.get("WEAVE_SENTRY_ENV"),
        "CI": session.env.get("CI"),
        "WB_SERVER_HOST": session.env.get("WB_SERVER_HOST"),
        "WF_CLICKHOUSE_HOST": session.env.get("WF_CLICKHOUSE_HOST"),
        "WEAVE_SERVER_DISABLE_ECOSYSTEM": session.env.get("WEAVE_SERVER_DISABLE_ECOSYSTEM"),
    }
    
    # Run tests
    if integration == "trace":
        session.run("pytest", *session.posargs, "tests/trace/", "trace/", env=env)
    elif integration == "trace_server":
        session.run("pytest", *session.posargs, "trace_server/", env=env)
    elif integration == "llamaindex":
        session.run("pytest", "-n4", *session.posargs, "integrations/llamaindex/", env=env)
    else:
        session.run("pytest", *session.posargs, f"integrations/{integration}/", env=env)

# Configure pytest
nox.options.sessions = ["tests", "lint", "integration_tests"]
nox.options.reuse_existing_virtualenvs = True
nox.options.stop_on_first_error = True