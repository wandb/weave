import typing
from ..api import op, mutation, Node
from .. import weave_types as types
from .. import op_def
from .. import panels


def op_get_return_type(uri):
    from .. import uris

    return uris.WeaveURI.parse(uri).to_ref().type


def op_get_return_type_from_inputs(inputs):
    return op_get_return_type(inputs["uri"].val)


@op(name="getReturnType", input_type={"uri": types.String()}, output_type=types.Type())
def get_returntype(uri):
    return op_get_return_type(uri)


# Hmm... This returns the same obj, not a ref anymore
# TODO: is this what we want?
@op(
    name="save",
    input_type={"obj": types.Any(), "name": types.String()},
    output_type=lambda input_types: input_types["obj"],
)
def save(obj, name):
    from . import storage

    ref = storage.save(obj, name=name)
    return ref.obj


@mutation
def _save(name, obj):
    from . import storage
    from .. import uris

    obj_uri = uris.WeaveURI.parse(name)

    # Clear the ref, otherwise save will immediately return
    # the result instead of saving the mutated result
    storage.clear_ref(obj)
    storage.save(obj, name=obj_uri.full_name)


@op(
    pure=False,
    setter=_save,
    name="get",
    input_type={"uri": types.String()},
    output_type=op_get_return_type_from_inputs,
)
def get(uri):
    from . import storage

    return storage.get(uri)


@op(
    # TODO: purity is a function of arguments in this special case.
    # E.g. if argument is "3 + 1", executing it is pure. If this matters
    # in practice, we can just hardcode in the engine.
    pure=False,
    name="execute",
    input_type={"node": types.Function({}, types.Any())},
    output_type=lambda input_type: input_type["node"].output_type,
)
def execute(node):
    from .. import weave_internal

    return weave_internal.use_internal(node)


class EcosystemTypedDict(typing.TypedDict):
    orgs: list[typing.Any]
    packages: list[typing.Any]
    datasets: list[typing.Any]
    models: list[typing.Any]
    ops: list[op_def.OpDef]


@op(render_info={"type": "function"})
def ecosystem() -> EcosystemTypedDict:
    from .. import registry_mem

    return {
        "orgs": [],
        "packages": [],
        "datasets": [],
        "models": [],
        "ops": registry_mem.memory_registry.list_ops(),
    }


@op()
def ecosystem_render(
    ecosystem: Node[EcosystemTypedDict],
) -> panels.Card:
    return panels.Card(
        title="Weave ecosystem",
        subtitle="",
        content=[
            # Have to do lots of type: ignore, because what we have here is a Node>
            # But it behaves like a TypedDict, because we mixin NodeMethodsClass for the
            # target type.
            # TODO: need to figure out a way to do this without breaking python types
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
                content=panels.Table(ecosystem["datasets"]),  # type: ignore
            ),
            panels.CardTab(
                name="Models", content=panels.Table(ecosystem["models"])  # type: ignore
            ),
            panels.CardTab(
                name="Ops",
                content=panels.Table(
                    ecosystem["ops"],  # type: ignore
                    columns=[
                        lambda op: op.op_name(),  # unfortunate, this is a VarNode attr
                        lambda op: op.output_type(),
                    ],
                ),
            ),
        ],
    )
