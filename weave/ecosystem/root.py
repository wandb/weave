import typing
from .. import api as weave

# TODO: Fix, these should be available from weave
from .. import ops
from .. import op_def
from .. import panels

from . import shap
from . import torchvision

# TODO: feels odd to call this "ops.Markdown".
# Maybe make it top level
# Or would types.Markdown by ok?
INTRO = ops.Markdown(
    """
# Welcome to Weave

*To understand intelligence: reflect!*

Weave is a new toolkit for constructing intelligent systems.

Click the links in the sidebar to get started.
"""
)


# TODO: using TypedDict here so we get automatic Object rendering
# But it'd be nice to use @weave.type() style so we have '.' attribute access instead
class EcosystemTypedDict(typing.TypedDict):
    orgs: list[typing.Any]
    packages: list[typing.Any]
    datasets: list[op_def.OpDef]
    models: list[typing.Any]
    ops: list[op_def.OpDef]


# TODO: This should be entirely lazy, so that we don't actually need to
# load anything to construct it. We can load when the user browsers to specific
# objects.
@weave.op(render_info={"type": "function"})
def ecosystem() -> EcosystemTypedDict:
    from .. import registry_mem

    return {
        "orgs": [],
        "packages": [],
        # This is not Weavey at all!  We should look for any registered ps of no arguments that produce DatasetCard type
        # We can do that query using... Weave, lazily. In fact, EcosystemType() doesn't need to store any data, just
        # render the panel. Which can lazily fetch / search for everything.
        "datasets": [shap.ca_housing_dataset, torchvision.mnist],
        "models": [],
        "ops": registry_mem.memory_registry.list_ops(),
    }


@weave.op()
def ecosystem_render(
    ecosystem: weave.Node[EcosystemTypedDict],
) -> panels.Card:
    return panels.Card(
        title="Weave ecosystem",
        subtitle="",
        content=[
            # Have to do lots of "type: ignore", because what we have here is a Node>
            # But it behaves like a TypedDict, because we mixin NodeMethodsClass for the
            # target type.
            # TODO: need to figure out a way to do this without breaking python types
            panels.CardTab(
                name="Intro",
                content=panels.Markdown(INTRO),  # type: ignore
            ),
            panels.CardTab(
                name="Organizations",
                content=panels.Table(ecosystem["orgs"]),  # type: ignore
            ),
            panels.CardTab(
                name="Packages",
                content=panels.Table(ecosystem["packages"]),  # type: ignore
            ),
            panels.CardTab(
                name="Datasets",
                content=panels.Table(
                    ecosystem["datasets"],  # type: ignore
                    columns=[
                        lambda op: op.op_name(),
                        lambda op: op.output_type(),
                    ],
                ),
            ),
            panels.CardTab(
                name="Models", content=panels.Table(ecosystem["models"])  # type: ignore
            ),
            panels.CardTab(
                name="Ops",
                content=panels.Table(
                    ecosystem["ops"],  # type: ignore
                    columns=[
                        lambda op: op.op_name(),
                        lambda op: op.output_type(),
                    ],
                ),
            ),
        ],
    )
