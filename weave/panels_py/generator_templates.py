"""
Contains the TemplateRegistry class, which is used to register
templates for the PyBoard generator. I think we might want to make
this even more generic and allow any panel to be a generator, but for 
now this is a simple abstraction that will work for basic use cases.

# TODO: Generalize this to work with panels like /weave/ecosystem/wandb/panel_time_series.py
# Proper panels have the following advantageous patterns:
1. They can create default configs from inputs
2. They can declare their own config editor rendering function
3. Their render function is pre-defined
4. If we make it work with the panel pattern, presumably it will be more general
   and lend itself to ui-driven generation of panels.

However, this current implementation is simple and easy to refactor.
"""


import dataclasses
import typing

from .. import graph
from .. import weave_types
from .. import registry_mem
from .. import decorator_op


@dataclasses.dataclass
class TemplateRegistrySpec:
    display_name: str
    description: str
    op_name: str
    input_node_predicate: typing.Optional[
        typing.Callable[[graph.Node[typing.Any]], bool]
    ] = None
    config_type: typing.Optional[weave_types.Type] = None
    is_featured: typing.Optional[bool] = None
    instructions_md: typing.Optional[str] = None
    thumbnail_url: typing.Optional[str] = None


@dataclasses.dataclass
class _TemplateRegistry:
    _specs: typing.Dict[str, TemplateRegistrySpec] = dataclasses.field(
        default_factory=dict
    )

    def register(
        self,
        op_name: str,
        display_name: str,
        description: str,
        *,
        input_node_predicate: typing.Optional[
            typing.Callable[[graph.Node[typing.Any]], bool]
        ] = None,
        config_type: typing.Optional[weave_types.Type] = None,
        is_featured: typing.Optional[bool] = None,
        instructions_md: typing.Optional[str] = None,
        thumbnail_url: typing.Optional[str] = None,
    ) -> None:
        return self.register_spec(
            TemplateRegistrySpec(
                display_name=display_name,
                description=description,
                op_name=op_name,
                input_node_predicate=input_node_predicate,
                config_type=config_type,
                is_featured=is_featured,
                instructions_md=instructions_md,
                thumbnail_url=thumbnail_url,
            )
        )

    def register_spec(self, spec: TemplateRegistrySpec) -> None:
        if spec.op_name in self._specs:
            raise ValueError(f"Template {spec.op_name} already registered")
        self._specs[spec.op_name] = spec

    def get_spec(self, name: str) -> TemplateRegistrySpec:
        return self._specs[name]

    def get_specs(self) -> typing.Dict[str, TemplateRegistrySpec]:
        return {**self._specs}


class PyBoardGeneratorSpec(typing.TypedDict):
    display_name: str
    description: str
    op_name: str
    config_type: typing.Optional[weave_types.Type]
    instructions_md: typing.Optional[str]
    thumbnail_url: typing.Optional[str]


# Processes have a singleton TemplateRegistry
template_registry = _TemplateRegistry()


@decorator_op.op(name="py_board-get_board_templates_for_node", hidden=True)  # type: ignore
def get_board_templates_for_node(
    input_node: graph.Node[typing.Any],
) -> list[PyBoardGeneratorSpec]:
    final_specs = []
    for op_name, spec in template_registry.get_specs().items():
        op = registry_mem.memory_registry._ops[op_name]
        if op.input_type.first_param_valid(input_node.type):
            predicate = spec.input_node_predicate
            if predicate is None or predicate(input_node):
                final_specs.append(
                    PyBoardGeneratorSpec(
                        display_name=spec.display_name,
                        description=spec.description,
                        op_name=spec.op_name,
                        config_type=spec.config_type,
                        instructions_md=spec.instructions_md,
                        thumbnail_url=spec.thumbnail_url,
                    )
                )
    return final_specs


@decorator_op.op(name="py_board-get_featured_board_templates", hidden=True)  # type: ignore
def get_featured_board_templates() -> list[PyBoardGeneratorSpec]:
    final_specs = []
    for op_name, spec in template_registry.get_specs().items():
        if spec.is_featured and spec.instructions_md:
            final_specs.append(
                PyBoardGeneratorSpec(
                    display_name=spec.display_name,
                    description=spec.description,
                    op_name=spec.op_name,
                    config_type=spec.config_type,
                    instructions_md=spec.instructions_md,
                    thumbnail_url=spec.thumbnail_url,
                )
            )
    return final_specs
