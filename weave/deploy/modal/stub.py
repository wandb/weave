from modal import Image, Secret, Stub, asgi_app
from weave.uris import WeaveURI
from weave.deploy.util import safe_name
import os

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
def fastapi_app():
    from weave.serve_fastapi import object_method_app
    from weave.uris import WeaveURI
    from weave import api

    uri = WeaveURI.parse(os.environ["MODEL_REF"])
    app = object_method_app(uri.to_ref(), auth_entity=os.environ.get("AUTH_ENTITY"))

    api.init(os.environ["PROJECT_NAME"])
    # TODO: hookup / provide more control over attributes
    # with api.attributes({"env": env}):
    return app
