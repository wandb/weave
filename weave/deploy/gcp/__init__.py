import os
from pathlib import Path
import sys
import shutil
import string
import subprocess
import typing
import tempfile

from weave.artifact_wandb import WeaveWBArtifactURI
from ..util import execute, safe_name
from weave import environment, __version__
from weave.uris import WeaveURI


def generate_dockerfile(
    model_ref: str,
    model_method: typing.Optional[str] = None,
    project_name: typing.Optional[str] = None,
    auth_entity: typing.Optional[str] = None,
    base_image: typing.Optional[str] = "python:3.11",
) -> str:
    """Generates a Dockerfile to run the weave op"""
    if project_name is None:
        ref_uri = WeaveURI.parse(model_ref)
        if not isinstance(ref_uri, WeaveWBArtifactURI):
            raise ValueError(f"Expected a wandb artifact ref, got {type(ref_uri)}")
        project_name = ref_uri.project_name
    src = Path(__file__).parent.parent / "Dockerfile"
    template = string.Template(src.read_text())

    return template.substitute(
        {
            "PROJECT_NAME": project_name,
            "BASE_IMAGE": base_image,
            "MODEL_REF": model_ref,
            "MODEL_METHOD": model_method or "",
            "AUTH_ENTITY": auth_entity or "",
        }
    )


def generate_requirements_txt(model_ref: str, dir: str, dev: bool = False) -> str:
    """Generate a requirements.txt file."""
    cwd = Path(os.getcwd())
    if dev and (cwd / "build_dist.py").exists():
        print("Building weave for development...")
        env = os.environ.copy()
        env.update({"WEAVE_SKIP_BUILD": "1"})
        execute([sys.executable, str(cwd / "build_dist.py")], env=env, capture=False)
        wheel = f"weave-{__version__}-py3-none-any.whl"
        execute(["cp", str(cwd / "dist" / wheel), dir], capture=False)
        weave = f"/app/{wheel}"
    else:
        weave = "weave @ git+https://github.com/wandb/weave@master"
    # TODO: add any additional reqs the op needs

    # We're requiring faiss-cpu for now here, to get Hooman Slackbot deploy
    # working. But this is not right, objects and ops should have their own
    # requirements that we compile together here.
    # TODO: Fix
    return f"""
uvicorn[standard]
fastapi
faiss-cpu
{weave}
"""


def gcloud(
    args: list[str],
    timeout: typing.Optional[float] = None,
    input: typing.Optional[str] = None,
    capture: bool = True,
) -> typing.Any:
    gcloud_absolute_path = shutil.which("gcloud")
    if gcloud_absolute_path is None:
        raise ValueError(
            "gcloud command required: https://cloud.google.com/sdk/docs/install"
        )
    if os.getenv("DEBUG") == "true":
        print(f"Running gcloud {' '.join(args)}")
    return execute(
        [gcloud_absolute_path] + args, timeout=timeout, capture=capture, input=input
    )


def enforce_login() -> None:
    """Ensure the user is logged in to gcloud."""
    try:
        auth = gcloud(["auth", "print-access-token", "--format=json"], timeout=3)
        if auth.get("token") is None:
            raise ValueError()
    except (subprocess.TimeoutExpired, ValueError):
        raise ValueError("Not logged in to gcloud. Please run `gcloud auth login`.")


def compile(
    model_ref: str,
    model_method: typing.Optional[str] = None,
    wandb_project: typing.Optional[str] = None,
    auth_entity: typing.Optional[str] = None,
    base_image: typing.Optional[str] = None,
    dev: bool = False,
) -> str:
    """Compile the weave application."""
    dir = tempfile.mkdtemp()
    reqs = os.path.join(dir, "requirements")
    os.mkdir(reqs)
    with open(os.path.join(reqs, "requirements.txt"), "w") as f:
        f.write(generate_requirements_txt(model_ref, reqs, dev))
    with open(os.path.join(dir, "Dockerfile"), "w") as f:
        f.write(
            generate_dockerfile(
                model_ref, model_method, wandb_project, auth_entity, base_image
            )
        )
    return dir


def ensure_service_account(
    name: str = "weave-default", project: typing.Optional[str] = None
) -> str:
    """Ensure the user has a service account."""
    if len(name) < 6 or len(name) > 30:
        raise ValueError("Service account name must be between 6 and 30 characters.")
    project = project or gcloud(["config", "get", "project", "--format=json"])
    account = gcloud(["auth", "list", "--filter=status:ACTIVE", "--format=json"])[0][
        "account"
    ]
    sa = f"{name}@{project}.iam.gserviceaccount.com"
    exists = gcloud(
        ["iam", "service-accounts", "list", f"--filter=email={sa}", "--format=json"]
    )
    if len(exists) == 0:
        print(f"Creating service account {name}...")
        display_name = (
            " ".join([n.capitalize() for n in name.split("-")]) + " Service Account"
        )
        gcloud(
            [
                "iam",
                "service-accounts",
                "create",
                name,
                f"--display-name={display_name}",
                f"--project={project}",
                "--format=json",
            ]
        )
        gcloud(
            [
                "iam",
                "service-accounts",
                "add-iam-policy-binding",
                f"{sa}",
                f"--project={project}",
                f"--member=user:{account}",
                "--role=roles/iam.serviceAccountUser",
                "--format=json",
            ]
        )
        print(
            "To grant additional permissions, run add-iam-policy-binding on the resource:"
        )
        print(
            "  gcloud storage buckets add-iam-policy-binding gs://BUCKET --member=serviceAccount:{sa} --role=ROLE"
        )
    else:
        print(f"Using service account: {sa}")
    return sa


def ensure_secret(
    name: str, value: str, service_account: str, project: typing.Optional[str] = None
) -> None:
    """Ensure a secret exists and is accessbile by the service account."""
    project = project or gcloud(["config", "get", "project", "--format=json"])
    exists = gcloud(
        [
            "secrets",
            "list",
            f"--filter=name~^.*\/{name}$",
            f"--project={project}",
            "--format=json",
        ]
    )
    if len(exists) == 0:
        print(f"Creating secret {name} and granting access to {service_account}...")
        gcloud(
            [
                "secrets",
                "create",
                name,
                f"--project={project}",
                "--replication-policy=automatic",
                "--format=json",
            ]
        )
    # To support changing service accounts, we always add secretAccessor
    gcloud(
        [
            "secrets",
            "add-iam-policy-binding",
            name,
            f"--project={project}",
            "--format=json",
            f"--member=serviceAccount:{service_account}",
            "--role=roles/secretmanager.secretAccessor",
        ]
    )
    gcloud(
        [
            "secrets",
            "versions",
            "add",
            name,
            f"--project={project}",
            "--format=json",
            "--data-file=-",
        ],
        input=value,
    )


# This is a sketch or the commands needed to downscope permissions and use secrets
def deploy(
    model_ref: str,
    model_method: typing.Optional[str] = None,
    wandb_project: typing.Optional[str] = None,
    gcp_project: typing.Optional[str] = None,
    region: typing.Optional[str] = None,
    service_account: typing.Optional[str] = None,
    auth_entity: typing.Optional[str] = None,
    base_image: typing.Optional[str] = "python:3.11",
    memory: typing.Optional[str] = "500Mi",
) -> None:
    """Deploy the weave application."""
    enforce_login()
    if region is None:
        region = gcloud(["config", "get", "compute/region", "--format=json"])
        if region is []:
            raise ValueError(
                "No default region set. Run `gcloud config set functions/region <region>` or set the region argument."
            )
    if service_account is None:
        try:
            service_account = ensure_service_account(project=gcp_project)
        except ValueError:
            print(
                "WARNING: No service account specified.  Using the compute engine default service account..."
            )
    dir = compile(model_ref, model_method, wandb_project, auth_entity, base_image)
    ref = WeaveURI.parse(model_ref)
    if not isinstance(ref, WeaveWBArtifactURI):
        raise ValueError(f"Expected a wandb artifact ref, got {type(ref)}")
    name = safe_name(f"{ref.project_name}-{ref.name}")
    project = wandb_project or ref.project_name
    key = environment.weave_wandb_api_key()
    secrets = {
        "WANDB_API_KEY": key,
    }
    if os.getenv("OPENAI_API_KEY"):
        secrets["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")
    args = [
        "run",
        "deploy",
        name,
        f"--region={region}",
        f"--memory={memory}",
        f"--set-env-vars=PROJECT_NAME={project}",
        f"--source={dir}",
        "--allow-unauthenticated",
    ]
    sec_or_env = ""
    if service_account is not None:
        args.append(f"--service-account={service_account}")
        sec_or_env = "--set-secrets="
        for k, v in secrets.items():
            if v is not None:
                ensure_secret(k, v, service_account, gcp_project)
                sec_or_env += f"{k}={k}:latest,"
    else:
        sec_or_env = "--set-env-vars="
        for k, v in secrets.items():
            sec_or_env += f"{k}={v},"
    # trim the trailing comma
    sec_or_env = sec_or_env[:-1]
    args.append(sec_or_env)
    if gcp_project is not None:
        args.append(f"--project={gcp_project}")
    gcloud(args, capture=False)
    shutil.rmtree(dir)


def develop(
    model_ref: str,
    model_method: typing.Optional[str] = None,
    base_image: typing.Optional[str] = "python:3.11",
    auth_entity: typing.Optional[str] = None,
) -> None:

    dir = compile(
        model_ref,
        model_method=model_method,
        base_image=base_image,
        auth_entity=auth_entity,
        dev=True,
    )
    name = safe_name(WeaveURI.parse(model_ref).name)
    docker = shutil.which("docker")
    if docker is None:
        raise ValueError("docker command required: https://docs.docker.com/get-docker/")
    print("Building container from: ", dir)
    execute(
        [docker, "buildx", "build", "-t", name, "--load", "."], cwd=dir, capture=False
    )
    env_api_key = environment.weave_wandb_api_key()
    if env_api_key is None:
        raise ValueError("WANDB_API_KEY environment variable required")
    env = {"WANDB_API_KEY": env_api_key}
    env.update(os.environ.copy())
    print("Running container at http://localhost:8080")
    execute(
        [
            docker,
            "run",
            "-p",
            "8080:8080",
            "-e",
            "WANDB_API_KEY",
            "-e",
            "OPENAI_API_KEY",
            name,
        ],
        env=env,
        capture=False,
    )
    if os.getenv("DEBUG") == None:
        print("Cleaning up...")
        shutil.rmtree(dir)
