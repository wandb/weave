import os
import typing

import click

from weave import __version__
from weave.deploy import gcp as google
from weave.trace import api
from weave.trace.refs import ObjectRef, parse_uri

# TODO: does this work?
os.environ["PYTHONUNBUFFERED"] = "1"


@click.group()
@click.version_option(version=__version__)
def cli() -> None:
    pass


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
    parsed_ref = parse_uri(model_ref)
    if not isinstance(parsed_ref, ObjectRef):
        raise ValueError(f"Expected a weave artifact uri, got {parsed_ref}")
    ref_project = parsed_ref.project
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
    from weave.deploy import modal as mdp

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
