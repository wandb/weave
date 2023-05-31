import typing
from .. import api as weave

# TODO: Fix, these should be available from weave
from .. import ops
from .. import op_def
from .. import panels
from .. import panel
from weave import context_state

loading_builtins_token = context_state.set_loading_built_ins()

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

from .. import registry_mem

op_org_name = registry_mem.memory_registry.get_op("user-name")


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
@weave.op(name="op-ecosystem", render_info={"type": "function"})
def ecosystem() -> Ecosystem:
    from .. import registry_mem

    return Ecosystem(
        _orgs=[],
        _packages=registry_mem.memory_registry.list_packages(),
        # This is not Weavey at all!  We should look for any registered ps of no arguments that produce DatasetCard type
        # We can do that query using... Weave, lazily. In fact, EcosystemType() doesn't need to store any data, just
        # render the panel. Which can lazily fetch / search for everything.
        # _datasets=[sklearn.ca_housing_dataset, torchvision.mnist],
        _datasets=[],
        _models=[],
        _ops=registry_mem.memory_registry.list_ops(),
    )


@weave.type()
class EcosystemPanel(panel.Panel):
    id = "EcosystemPanel"
    input_node: weave.Node[Ecosystem]

    @weave.op()
    def render(self) -> panels.Card:
        ecosystem = self.input_node
        return panels.Card(
            title="Weave",
            subtitle="",
            content=[
                panels.CardTab(
                    name="Intro",
                    content=panels.PanelMarkdown(INTRO),  # type: ignore
                ),
                panels.CardTab(
                    name="Organizations",
                    content=panels.Table(
                        weave.save(
                            [
                                "wandb",
                                "huggingface",
                                "deepmind",
                                "blueriver",
                                "google",
                                "openai",
                                "microsoft",
                            ],
                            name="org_list",
                        ),
                        columns=[
                            lambda org_name: panels.WeaveLink(
                                org_name, lambda org_name: ops.entity(org_name)  # type: ignore
                            )  # type: ignore
                        ],
                    ),  # type: ignore
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


@weave.op(render_info={"type": "function"})
def make_string_cool(input: str) -> str:
    return "cool: " + input


from .langchain import ChatOpenAI


@weave.op(render_info={"type": "function"})
def chat_gpt(model_name: str, temperature: float) -> ChatOpenAI:
    return ChatOpenAI(model_name=model_name, temperature=temperature)


@weave.type()
class Package:
    name: str
    ops: list[op_def.OpDef]

    @weave.op()
    def package_name(self) -> str:
        # Needed becuase of "name" name collision (varNode)
        return self.name

    @weave.op()
    def op(self, name: str) -> op_def.OpDef:
        for op in self.ops:
            if op.name == name:
                return op
        raise ValueError(f"Op {name} not found in package {self.name}")


from . import langchain

packages = [
    Package(name="OpenAI", ops=[make_string_cool, langchain.chat_openai]),
]


@weave.op(render_info={"type": "function"})
def package(name: str) -> Package:
    for pack in packages:
        if pack.name == name:
            return pack
    raise ValueError(f"Package {name} not found")


@weave.type()
class PackagePanel(panel.Panel):
    id = "PackagePanel"
    input_node: weave.Node[Package]

    @weave.op()
    def render(self) -> panels.Card:
        pack = self.input_node
        return panels.Card(
            title=pack.name,
            subtitle="",
            content=[
                panels.CardTab(
                    name="Ops",
                    content=panels.Table(
                        pack.ops,
                        columns=[
                            lambda op: panels.WeaveLink(
                                op.op_name(),
                                vars={
                                    "package_name": pack.package_name(),
                                    "op_name": op.op_name(),
                                },
                                to=lambda input, vars: package(vars["package_name"]).op(
                                    vars["op_name"]
                                ),
                            ),
                            lambda op: op.output_type(),
                        ],
                    ),
                ),
            ],
        )


@weave.type()
class OpPanel(panel.Panel):
    id = "OpPanel"
    input_node: weave.Node[op_def.OpDef]

    @weave.op()
    def render(self) -> panels.Group:
        inputs = self.input_node.input_type()
        return panels.Group(
            items={
                "name": self.input_node.op_name(),
                "inputs": panels.Group(
                    items={
                        "name": "Paramaters",
                        "arg0": panels.StringEditor("hello"),
                        "arg1": panels.Slider(0.7),
                        "go": lambda arg0, arg1: panels.WeaveLink(
                            "Go!",
                            vars={
                                # "op": self.input_node.op_name(),
                                # "arg": value.value(),
                                "called": ops.call_op(
                                    self.input_node.op_name(),
                                    ops.dict_(input=arg0.value(), arg1=arg1.value()),
                                ),
                            },
                            to=lambda input, args: args["called"],
                        ),
                    }
                ),
            }
        )


context_state.clear_loading_built_ins(loading_builtins_token)
