from dataclasses import dataclass
import json
import os
import shutil
import subprocess
import typing
import tempfile
from weave import environment
from urllib import parse
import sys
# from ... import errors, environment

def gcloud(args: list[str], timeout: typing.Optional[float] = None, capture = True) -> typing.Any:
    gcloud_absolute_path = shutil.which('gcloud')
    if gcloud_absolute_path is None:
        raise ValueError("gcloud command required: https://cloud.google.com/sdk/docs/install")
    if os.getenv("DEBUG") == "true":
        print(f"Running gcloud {' '.join(args)}")
    process = subprocess.Popen(
        [ gcloud_absolute_path ] + args,
        stdout=subprocess.PIPE if capture else sys.stdout,
        stderr=subprocess.PIPE if capture else sys.stderr,
        stdin=subprocess.PIPE if capture else sys.stdin,
        universal_newlines=True,
    )
    out, err = process.communicate(timeout=timeout)
    if process.returncode != 0:
        raise ValueError(f"gcloud command failed: {err or ''}")
    
    if not capture:
        return None

    try:
        return json.loads(out)
    except json.JSONDecodeError:
        raise ValueError(f"Failed to parse JSON from gcloud: {out}")

def enforce_login():
    """Ensure the user is logged in to gcloud."""
    try:
        auth = gcloud(["auth", "print-access-token", "--format=json"], timeout=3)
        if auth.get("token") is None:
            raise ValueError()
    except (subprocess.TimeoutExpired, ValueError):
        raise ValueError("Not logged in to gcloud. Please run `gcloud auth login`.")


def compile() -> str:
    """Compile the weave application."""
    dir = tempfile.mkdtemp()
    cur_dir = os.path.dirname(os.path.realpath(__file__))
    shutil.copy(os.path.join(cur_dir, "main.py.template"), os.path.join(dir, "main.py"))
    with open(os.path.join(dir, "requirements.txt"), "w") as f:
        f.write("""functions-framework==3.*
mangum
weave @ git+https://github.com/wandb/weave@weaveflow
""")
    return dir

def deploy(model_ref: str,
           wandb_project: typing.Optional[str] = None, 
           gcp_project: typing.Optional[str] = None,
           region: typing.Optional[str] = None,
           runtime: typing.Optional[str] = "python311",
           memory: typing.Optional[str] = "500Mb"):
    """Deploy the weave application."""
    enforce_login()
    if region is None:
        region = gcloud(["config", "get", "compute/region", "--format=json"])
        if region is []:
            raise ValueError("No default region set. Run `gcloud config set functions/region <region>` or set the region argument.")
    dir = compile()
    ref = Ref.from_ref(model_ref)
    name = f"{ref.project}-{ref.name}"
    project = wandb_project or ref.project
    key = environment.weave_wandb_api_key()
    #TODO: SECRET ENV VARS
    args = [
        "functions",
        "deploy",
        name,
        "--gen2",
        f"--region={region}",
        f"--memory={memory}",
        f"--runtime={runtime}",
        f"--set-env-vars=WANDB_API_KEY={key},MODEL_REF={model_ref},WANDB_PROJECT={project},OPENAI_API_KEY={os.getenv('OPENAI_API_KEY')}",
        f"--source={dir}",
        "--entry-point=api",
        "--trigger-http",
        "--allow-unauthenticated",
        "--format=json"
    ]
    if gcp_project is not None:
        args.append(f"--project={gcp_project}")
    gcloud(args, capture=False)
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
