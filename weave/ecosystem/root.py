import typing
from .. import api as weave

# TODO: Fix, these should be available from weave
from .. import ops
from .. import op_def
from .. import panels
from weave import context_state

loading_builtins_token = context_state.set_loading_built_ins()

from . import bertviz

from . import xgboost
from . import shap

# from . import sklearn
from . import keras
from . import torchvision
from . import huggingface

from . import craiyon

from . import spacy
from . import lens
from . import wandb
from . import scenario
from . import shawn
from . import wandb
from . import replicate
from . import openai

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
@weave.type()
class Ecosystem:
    _orgs: list[typing.Any]
    _packages: list[op_def.OpDef]
    _datasets: list[op_def.OpDef]
    _models: list[typing.Any]
    _ops: list[op_def.OpDef]

    @weave.op()
    def orgs(self) -> list[typing.Any]:
        return self._orgs

    @weave.op()
    def packages(self) -> list[op_def.OpDef]:
        return self._packages

    @weave.op()
    def datasets(self) -> list[op_def.OpDef]:
        return self._datasets

    @weave.op()
    def models(self) -> list[typing.Any]:
        return self._models

    @weave.op()
    def ops(self) -> list[op_def.OpDef]:
        return self._ops


# TODO: This should be entirely lazy, so that we don't actually need to
# load anything to construct it. We can load when the user browsers to specific
# objects.
@weave.op(render_info={"type": "function"})
def ecosystem() -> Ecosystem:
    from .. import registry_mem

    return Ecosystem(
        _orgs=[],
        _packages=registry_mem.memory_registry.list_packages(),
        # This is not Weavey at all!  We should look for any registered ps of no arguments that produce DatasetCard type
        # We can do that query using... Weave, lazily. In fact, EcosystemType() doesn't need to store any data, just
        # render the panel. Which can lazily fetch / search for everything.
        _datasets=[sklearn.ca_housing_dataset, torchvision.mnist],
        _models=[],
        _ops=registry_mem.memory_registry.list_ops(),
    )


@weave.op()
def ecosystem_render(
    ecosystem: weave.Node[Ecosystem],
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
                content=panels.PanelMarkdown(INTRO),  # type: ignore
            ),
            panels.CardTab(
                name="Organizations",
                content=panels.Table(ecosystem.orgs()),  # type: ignore
            ),
            panels.CardTab(
                name="Packages",
                content=panels.Table(
                    ecosystem.packages(),  # type: ignore
                    columns=[
                        lambda pack: panels.WeaveLink(
                            pack.op_name(),
                            vars={"package_root_op": ops.call_op(pack.op_name())},
                            to=lambda input, vars: vars["package_root_op"],
                        ),
                        lambda pack: pack.output_type(),
                    ],
                ),
            ),
            panels.CardTab(
                name="Datasets",
                content=panels.Table(
                    ecosystem.datasets(),  # type: ignore
                    columns=[
                        lambda op: op.op_name(),
                        lambda op: op.output_type(),
                    ],
                ),
            ),
            panels.CardTab(
                name="Models", content=panels.Table(ecosystem.models())  # type: ignore
            ),
            panels.CardTab(
                name="Ops",
                content=panels.Table(
                    ecosystem.ops(),  # type: ignore
                    columns=[
                        lambda op: op.op_name(),
                        lambda op: op.output_type(),
                    ],
                ),
            ),
        ],
    )


context_state.clear_loading_built_ins(loading_builtins_token)
