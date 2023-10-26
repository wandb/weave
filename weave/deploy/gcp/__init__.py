from dataclasses import dataclass
import json
import os
from pathlib import Path
import shutil
import subprocess
import typing
import tempfile
from weave import environment, __version__
from weave.uris import WeaveURI
from urllib import parse
import sys

DOCKER_FILE = """
FROM python:3.11
"""

def generate_dockerfile(model_ref: str, 
                        project_name: typing.Optional[str] = None, 
                        base_image: typing.Optional[str] = "python:3.11") -> str:
    """Generates a Dockerfile to run the weave op"""
    if project_name is None:
        project_name = WeaveURI.parse(model_ref).project_name
    return f"""
FROM {base_image}

ENV PYTHONUNBUFFERED 1
WORKDIR /app

COPY requirements/* .
RUN pip install --no-cache-dir -r requirements.txt
ENV PROJECT_NAME {project_name}

EXPOSE 8080
CMD ["weave", "serve", "{model_ref}", "--port=8080"]
"""

def generate_requirements_txt(model_ref: str, dir: str, dev = False) -> str:
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
        weave = "weave @ git+https://github.com/wandb/weave@weaveflow"
    # TODO: add any additional reqs the op needs
    return f"""
uvicorn[standard]
fastapi
{weave}
"""

def execute(args: list[str], 
            timeout: typing.Optional[float] = None, 
            cwd: typing.Optional[str] = None,
            env: typing.Optional[dict[str, str]] = None, 
            capture = True) -> typing.Any:
    process = subprocess.Popen(
        args,
        stdout=subprocess.PIPE if capture else sys.stdout,
        stderr=subprocess.PIPE if capture else sys.stderr,
        stdin=subprocess.PIPE if capture else sys.stdin,
        universal_newlines=True,
        env=env or os.environ.copy(),
        cwd=cwd
    )
    out, err = process.communicate(timeout=timeout)
    if process.returncode != 0:
        raise ValueError(f"Command failed: {err or ''}")
    
    if not capture:
        return None

    try:
        return json.loads(out)
    except json.JSONDecodeError:
        raise ValueError(f"Failed to parse JSON from command: {out}")

def gcloud(args: list[str], timeout: typing.Optional[float] = None, capture = True) -> typing.Any:
    gcloud_absolute_path = shutil.which('gcloud')
    if gcloud_absolute_path is None:
        raise ValueError("gcloud command required: https://cloud.google.com/sdk/docs/install")
    if os.getenv("DEBUG") == "true":
        print(f"Running gcloud {' '.join(args)}")
    return execute([gcloud_absolute_path] + args, timeout=timeout, capture=capture)

def enforce_login():
    """Ensure the user is logged in to gcloud."""
    try:
        auth = gcloud(["auth", "print-access-token", "--format=json"], timeout=3)
        if auth.get("token") is None:
            raise ValueError()
    except (subprocess.TimeoutExpired, ValueError):
        raise ValueError("Not logged in to gcloud. Please run `gcloud auth login`.")

def compile(model_ref: str, wandb_project: typing.Optional[str] = None, base_image: typing.Optional[str] = None, dev = False) -> str:
    """Compile the weave application."""
    dir = tempfile.mkdtemp()
    reqs = os.path.join(dir, "requirements")
    os.mkdir(reqs)
    with open(os.path.join(reqs, "requirements.txt"), "w") as f:
        f.write(generate_requirements_txt(model_ref, reqs, dev))
    with open(os.path.join(dir, "Dockerfile"), "w") as f:
        f.write(generate_dockerfile(model_ref, wandb_project, base_image))
    return dir

def deploy(model_ref: str,
           wandb_project: typing.Optional[str] = None, 
           gcp_project: typing.Optional[str] = None,
           region: typing.Optional[str] = None,
           base_image: typing.Optional[str] = "python:3.11",
           memory: typing.Optional[str] = "500Mb"):
    """Deploy the weave application."""
    enforce_login()
    if region is None:
        region = gcloud(["config", "get", "compute/region", "--format=json"])
        if region is []:
            raise ValueError("No default region set. Run `gcloud config set functions/region <region>` or set the region argument.")
    dir = compile(model_ref, wandb_project)
    ref = WeaveURI.parse(model_ref)
    name = f"{ref.project_name}-{ref.name}"
    project = wandb_project or ref.project_name
    key = environment.weave_wandb_api_key()
    args = [
        "run",
        "deploy",
        name,
        f"--region={region}",
        f"--memory={memory}",
        f"--set-env-vars=PROJECT_NAME={project}",
        f"--set-secrets=WANDB_API_KEY={key},OPENAI_API_KEY={os.getenv('OPENAI_API_KEY')}",
        f"--source={dir}",
        "--allow-unauthenticated",
    ]
    if gcp_project is not None:
        args.append(f"--project={gcp_project}")
    gcloud(args, capture=False)
    shutil.rmtree(dir)

def develop(model_ref: str, base_image: typing.Optional[str] = "python:3.11"):
    dir = compile(model_ref, base_image=base_image, dev=True)
    name = WeaveURI.parse(model_ref).name
    docker = shutil.which("docker")
    if docker is None:
        raise ValueError("docker command required: https://docs.docker.com/get-docker/")
    print("Building container from: ", dir)
    execute([docker, "buildx", "build", "-t", name, "--load", "."], cwd=dir, capture=False)
    env = {"WANDB_API_KEY": environment.weave_wandb_api_key()}
    env.update(os.environ.copy())
    print("Running container at http://localhost:8080")
    execute([docker, "run", "-p", "8080:8080", "-e", "WANDB_API_KEY", "-e", "OPENAI_API_KEY", name], env=env, capture=False)
    if os.getenv("DEBUG") == None:
        print("Cleaning up...")
        shutil.rmtree(dir)

@dataclass
class Ref:
    source: str
    entity: str
    project: str
    name: str
    version: str

    @classmethod
    def from_ref(cls, model_ref: str) -> 'Ref':
        scheme, _, path, _, _, _ = parse.urlparse(model_ref)
        parts = path.strip("/").split("/")
        parts = [parse.unquote(part) for part in parts]
        if len(parts) < 3:
            raise ValueError(f"Invalid WB Artifact URI: {model_ref}")
        name, version = parts[2].split(":")
        return cls(source=scheme,
                   entity=parts[0],
                   project=parts[1],
                   name=name, version=version)
