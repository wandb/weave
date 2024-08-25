import weave
from weave.legacy.weave import box, graph
from weave.legacy.weave import context_state as _context_state
from weave.legacy.weave import weave_types as types
from weave.legacy.weave.language_features.tagging import tag_store
from weave.legacy.weave.language_features.tagging.tagged_value_type import TaggedValueType

tag_adders = 0


def op_add_tag(obj_node: graph.Node, tags: dict[str, str]):  # type: ignore[no-untyped-def]
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
    def custom_tagger(obj):  # type: ignore[no-untyped-def]
        return tag_store.add_tags(
            box.box(obj), {f"_ct_{k}": v for k, v in tags.items()}
        )

    _context_state.clear_loading_built_ins(_loading_builtins_token)

    return custom_tagger(obj_node)


def make_get_tag(tag_name: str):  # type: ignore[no-untyped-def]
    from weave.legacy.weave.language_features.tagging import make_tag_getter_op

    return make_tag_getter_op.make_tag_getter_op(f"_ct_{tag_name}", types.String())
