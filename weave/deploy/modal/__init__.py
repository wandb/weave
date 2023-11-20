import os
from pathlib import Path
import string
import time
import typing
import tempfile
from weave.uris import WeaveURI
from weave import artifact_wandb, environment

try:
    from modal.config import config
    from modal.runner import deploy_stub
    from modal.serving import serve_stub
    from modal.cli.import_refs import import_stub
    import dotenv
except ImportError:
    raise ImportError(
        "modal must be installed and configured: \n  pip install weave[modal]\n  modal setup"
    )


def compile(
    model_ref: str,
    project: str,
    reqs: list[str],
    auth_entity: typing.Optional[str] = None,
    secrets: typing.Optional[dict[str, str]] = None,
) -> Path:
    """Generates a modal py file and secret env vars to run the weave op"""
    dir = Path(tempfile.mkdtemp())
    with open(Path(__file__).parent / "stub.py", "r") as f:
        template = string.Template(f.read())
        src = template.substitute(
            {
                "REQUIREMENTS": '", "'.join(reqs),
                "MODEL_REF": model_ref,
                "PROJECT_NAME": project,
                "AUTH_ENTITY": auth_entity or "",
            }
        )

    with open(dir / "weave_model.py", "w") as f:
        f.write(src)
    with open(dir / ".env", "w") as f:
        if secrets is not None:
            for k, v in secrets.items():
                f.write(f"{k}={v}\n")
    return dir


def generate_modal_stub(
    model_ref: str,
    project_name: typing.Optional[str] = None,
    reqs: typing.Optional[list[str]] = None,
    auth_entity: typing.Optional[str] = None,
    secrets: typing.Optional[dict[str, str]] = None,
) -> str:
    """Generates a modal py file to run the weave op"""
    uri = WeaveURI.parse(model_ref)
    if project_name is None:
        if not isinstance(uri, artifact_wandb.WeaveWBArtifactURI):
            raise ValueError(f"Expected a wandb artifact ref, got {type(uri)}")
        project_name = uri.project_name

    parsed_ref = uri.to_ref()
    if not isinstance(parsed_ref, artifact_wandb.WandbArtifactRef):
        raise ValueError(f"Expected a wandb artifact ref, got {parsed_ref}")
    project = project_name or os.getenv("PROJECT_NAME")
    if project is None:
        raise ValueError(
            "project must be specified from command line or via the PROJECT_NAME env var"
        )
    reqs = reqs or []
    reqs.append("weave @ git+https://github.com/wandb/weave@weaveflow")
    reqs.append("fastapi>=0.104.0")
    return str(
        compile(model_ref, project, reqs, secrets=secrets, auth_entity=auth_entity)
        / "weave_model.py"
    )


def extract_secrets(model_ref: str) -> dict[str, str]:
    # TODO: get secrets from the weave op
    key = environment.weave_wandb_api_key()
    if key is None:
        secrets = {}
    else:
        secrets = {
            "WANDB_API_KEY": key,
        }
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if openai_api_key:
        secrets["OPENAI_API_KEY"] = openai_api_key
    return secrets


def deploy(
    model_ref: str,
    wandb_project: typing.Optional[str] = None,
    auth_entity: typing.Optional[str] = None,
) -> None:
    """Deploy a model to the modal labs cloud."""

    ref = generate_modal_stub(
        model_ref,
        wandb_project,
        secrets=extract_secrets(model_ref),
        auth_entity=auth_entity,
    )
    stub = import_stub(ref)
    deploy_stub(stub, name=stub.name, environment_name=config.get("environment"))


def develop(model_ref: str, auth_entity: typing.Optional[str] = None) -> None:
    """Run a model for testing."""
    ref = generate_modal_stub(
        model_ref, secrets=extract_secrets(model_ref), auth_entity=auth_entity
    )
    print(f"Serving live code from: {ref}")
    stub = import_stub(ref)
    timeout = 1800
    with serve_stub(stub, ref, environment_name=config.get("environment")):
        while timeout > 0:
            t = min(timeout, 3600)
            time.sleep(t)
            timeout -= t
