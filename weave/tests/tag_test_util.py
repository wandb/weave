import weave
from weave.legacy import box, graph
from weave.legacy import context_state as _context_state
from weave.legacy.language_features.tagging import tag_store
from weave.legacy.language_features.tagging.tagged_value_type import TaggedValueType

from .. import weave_types as types

tag_adders = 0


def op_add_tag(obj_node: graph.Node, tags: dict[str, str]):
    global tag_adders
    tag_adders += 1
    name = f"_custom_tagger_{tag_adders}"

    _loading_builtins_token = _context_state.set_loading_built_ins()

    @weave.op(
        name=name,
        input_type={"obj": types.Any()},
        output_type=lambda input_types: TaggedValueType(
            types.TypedDict({f"_ct_{k}": types.String() for k in tags.keys()}),
            input_types["obj"],
        ),
    )
    def custom_tagger(obj):
        return tag_store.add_tags(
            box.box(obj), {f"_ct_{k}": v for k, v in tags.items()}
        )

    _context_state.clear_loading_built_ins(_loading_builtins_token)

    return custom_tagger(obj_node)


def make_get_tag(tag_name: str):
    from weave.legacy.language_features.tagging import make_tag_getter_op

    return make_tag_getter_op.make_tag_getter_op(f"_ct_{tag_name}", types.String())
