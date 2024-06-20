import os

from fastapi import FastAPI
from modal import Image, Secret, Stub, asgi_app

from weave.deploy.util import safe_name
from weave.legacy.artifact_wandb import WandbArtifactRef
from weave.trace.refs import ObjectRef, parse_uri
from weave.uris import WeaveURI

image = (
    Image.debian_slim()
    .apt_install("git")
    .pip_install(["$REQUIREMENTS"])
    .env(
        {
            "MODEL_REF": "$MODEL_REF",
            "PROJECT_NAME": "$PROJECT_NAME",
            "AUTH_ENTITY": "$AUTH_ENTITY",
        }
    )
)
stub = Stub("$PROJECT_NAME")
uri = WeaveURI.parse("$MODEL_REF")


@stub.function(image=image, secret=Secret.from_dotenv(__file__))
@asgi_app(label=safe_name(uri.name))
def fastapi_app() -> FastAPI:
    from weave import api
    from weave.serve_fastapi import object_method_app
    from weave.uris import WeaveURI

    uri_ref = parse_uri(os.environ["MODEL_REF"])
    if not isinstance(uri_ref, ObjectRef):
        raise ValueError(f"Expected a weave object uri, got {type(uri_ref)}")
    app = object_method_app(uri_ref, auth_entity=os.environ.get("AUTH_ENTITY"))

    api.init(os.environ["PROJECT_NAME"])
    # TODO: hookup / provide more control over attributes
    # with api.attributes({"env": env}):
    return app
