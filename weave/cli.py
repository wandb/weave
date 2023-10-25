import click
import time
from weave import server, __version__

@click.group()
@click.version_option(version=__version__)
def cli(ctx):
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

@cli.group(help="Deploy weave models.")
def deploy():
    pass

@deploy.command(help="Deploy to GCP.")
@click.argument("model")
@click.option("--project", help="W&B project name.")
@click.option("--gcp-project", help="GCP project name.")
def gcp(model, project, gcp_project) -> None:
    print(f"Deploying model {model}...")
    print("Model deployed")

if __name__ == "__main__":
    cli()
