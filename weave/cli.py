import click
import os
import time
import typing
import sys
from weave import __version__

# from .model_server import app
from .urls import BROWSE3_PATH
from . import api
from . import uris
from . import artifact_wandb
from .deploy import gcp as google

# TODO: does this work?
os.environ["PYTHONUNBUFFERED"] = "1"


@click.group()
@click.version_option(version=__version__)
def cli() -> None:
    pass


@cli.command("ui", help="Start the weave UI.")
def start_ui() -> None:
    print("Starting server...")
    try:
        from weave import server
    except ModuleNotFoundError:
        print("Run 'pip install weave[engine]' to use the local server.")
        sys.exit(1)
    serv = server.HttpServer(port=3000)  # type: ignore
    serv.start()
    print("Server started")
    print(f"http://localhost:3000/{BROWSE3_PATH}")
    while True:
        time.sleep(10)


@cli.command(help="Serve weave models.")
@click.argument("model_ref")
@click.option("--method", help="Method name to serve.")
@click.option("--project", help="W&B project name.")
@click.option("--env", default="development", help="Environment to tag the model with.")
@click.option(
    "--auth-entity", help="Enforce authorization for this entity using W&B API keys."
)
@click.option("--port", default=9996, type=int)
def serve(
    model_ref: str,
    method: typing.Optional[str],
    auth_entity: typing.Optional[str],
    project: str,
    env: str,
    port: int,
) -> None:
    parsed_uri = uris.WeaveURI.parse(model_ref)
    if not isinstance(parsed_uri, artifact_wandb.WeaveWBArtifactURI):
        raise ValueError(f"Expected a weave artifact uri, got {parsed_uri}")
    parsed_ref = parsed_uri.to_ref()
    ref_project = parsed_uri.project_name
    project_override = project or os.getenv("PROJECT_NAME")
    if project_override:
        print(f"Logging to project different from {ref_project}")
        project = project_override
    else:
        project = ref_project

    api.init(project)
    # TODO: provide more control over attributes
    with api.attributes({"env": env}):
        api.serve(
            parsed_ref, method_name=method or None, auth_entity=auth_entity, port=port
        )


@cli.group(help="Deploy weave models.")
def deploy() -> None:
    pass


@deploy.command(help="Deploy to GCP.")
@click.argument("model_ref")
@click.option("--method", help="Method name to serve.")
@click.option("--project", help="W&B project name.")
@click.option("--gcp-project", help="GCP project name.")
@click.option(
    "--auth-entity", help="Enforce authorization for this entity using W&B API keys."
)
@click.option("--service-account", help="GCP service account.")
@click.option("--dev", is_flag=True, help="Run the function locally.")
def gcp(
    model_ref: str,
    method: str,
    project: str,
    gcp_project: str,
    auth_entity: str,
    service_account: str,
    dev: bool = False,
) -> None:
    if dev:
        print(f"Developing model {model_ref}...")
        google.develop(model_ref, model_method=method, auth_entity=auth_entity)
        return
    print(f"Deploying model {model_ref}...")
    if auth_entity is None:
        print(
            "WARNING: No --auth-entity specified.  This endpoint will be publicly accessible."
        )
    try:
        google.deploy(
            model_ref,
            model_method=method,
            wandb_project=project,
            auth_entity=auth_entity,
            gcp_project=gcp_project,
            service_account=service_account,
        )
    except ValueError as e:
        if os.getenv("DEBUG") == "true":
            raise e
        else:
            raise click.ClickException(
                str(e) + "\nRun with DEBUG=true to see full exception."
            )
    print("Model deployed")


@deploy.command(help="Deploy to Modal Labs.")
@click.argument("model_ref")
@click.option("--project", help="W&B project name.")
@click.option(
    "--auth-entity", help="Enforce authorization for this entity using W&B API keys."
)
@click.option("--dev", is_flag=True, help="Run the function locally.")
def modal(model_ref: str, project: str, auth_entity: str, dev: bool = False) -> None:
    from .deploy import modal as mdp

    if dev:
        print(f"Developing model {model_ref}...")
        mdp.develop(model_ref, auth_entity=auth_entity)
        return
    print(f"Deploying model {model_ref}...")
    if auth_entity is None:
        print(
            "WARNING: No --auth-entity specified.  This endpoint will be publicly accessible."
        )
    try:
        mdp.deploy(model_ref, wandb_project=project, auth_entity=auth_entity)
    except ValueError as e:
        if os.getenv("DEBUG") == "true":
            raise e
        else:
            raise click.ClickException(
                str(e) + "\nRun with DEBUG=true to see full exception."
            )
    print("Model deployed")


if __name__ == "__main__":
    cli()
