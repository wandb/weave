import click
import time
import typing
from weave import server, __version__
import uvicorn
import os

# from .model_server import app
from . import api
from . import uris
from . import artifact_wandb


@click.group()
@click.version_option(version=__version__)
def cli() -> None:
    pass


@cli.command("ui", help="Start the weave UI.")
def start_ui() -> None:
    print("Starting server...")
    serv = server.HttpServer(port=3000)  # type: ignore
    serv.start()
    print("Server started")
    print("http://localhost:3000/browse2")
    while True:
        time.sleep(10)


@cli.command(help="Serve weave models.")
@click.argument("model_ref")
@click.option("--method", help="Method name to serve.")
@click.option("--project", help="W&B project name.")
@click.option("--port", default=9996, type=int)
def serve(
    model_ref: str, method: typing.Optional[str], project: str, port: int
) -> None:
    print(f"Serving {model_ref}")
    parsed_ref = uris.WeaveURI.parse(model_ref).to_ref()
    if not isinstance(parsed_ref, artifact_wandb.WandbArtifactRef):
        raise ValueError(f"Expected a wandb artifact ref, got {parsed_ref}")
    api.init(project)
    # TODO: provide more control over attributes
    with api.attributes({"env": "production"}):
        api.serve(parsed_ref, method_name=method, port=port)


@cli.group(help="Deploy weave models.")
def deploy() -> None:
    pass


@deploy.command(help="Deploy to GCP.")
@click.argument("model_ref")
@click.option("--project", help="W&B project name.")
@click.option("--gcp-project", help="GCP project name.")
def gcp(model_ref: str, project: str, gcp_project: str) -> None:
    print(f"Deploying model {model_ref}...")
    print("Model deployed")


if __name__ == "__main__":
    cli()
