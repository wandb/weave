import dataclasses
import itertools
import typing
import weave
from weave import weave_internal
from weave import registry_mem
from weave import op_args


def test_all_types():
    trees = build_trees(2)
    res = weave.use(trees)
    print("Done!")


@dataclasses.dataclass
class TypeFuzzManager:
    # specs: dict[typing.Type[weave.types.Type], dict[weave.types.Type, list[typing.Any]]]
    raw_specs: list[typing.Any] = dataclasses.field(default_factory=list)

    def add_spec(self, type: weave.types.Type, value: typing.Any):
        self.raw_specs.append((type, value))
        # fuzzer_key = type.__class__
        # type_key = type
        # if fuzzer_key not in self.specs:
        #     self.specs[fuzzer_key] = {}
        # if type_key not in self.specs[fuzzer_key]:
        #     self.specs[fuzzer_key][type_key] = []
        # self.specs[fuzzer_key][type_key].append(value)


manager = TypeFuzzManager()

manager.add_spec(weave.types.Int(), 42)
manager.add_spec(weave.types.String(), "Hello World")

disallowed_ops = set(
    [
        "get",
        "mapped-get",
        "getReturnType",
        "localpath",
        "localpathReturnType",
        "op-used_by",
        "op-objects",
        "mapped-localpathReturnType_unioned",
        "mapped-localpath",
        "localpathReturnType_unioned",
        "getReturnType_unioned",
        "mapped-getReturnType_unioned",
        "mapped-getReturnType_unioned",
        "sqlconnection-table",
        "sqlconnection-table"
        # these ops have a constraint on the inputs which makes fuzzing it hard
        # It would be nice to have a special error for param validation that can
        # be caught and handled correctly
        "op-number_bins_fixed",
        "mapped_op-number_bins_fixed",
        "numbers-binsequal",
    ]
)


def build_trees(depth: int = 3):
    roots = [
        weave_internal.make_const_node(spec[0], spec[1]) for spec in manager.raw_specs
    ]

    for i in range(depth):
        working_list = []
        for root in roots:
            root_added = False
            if isinstance(root.type, weave.types.Function):
                # TODO: Figure this out
                continue
            next_ops = registry_mem.memory_registry.find_chainable_ops(root.type)
            for op in next_ops:
                if op.name in disallowed_ops:
                    continue
                elif op.name.startswith("root-") or op.name.startswith("rpt_"):
                    # Wow - we don't have any protection from calling gql ops
                    # with non-consts
                    continue
                if isinstance(op.input_type, op_args.OpNamedArgs):
                    all_named_args = op.input_type.named_args()
                    needed_types = all_named_args[1:]
                    if len(needed_types) == 0:
                        root_added = True
                        working_list.append(op(root))
                    else:
                        all_possible_params = [[root]]
                        for needed_type in needed_types:
                            at_least_one = False
                            new_possible_params = []
                            for spec in manager.raw_specs:
                                if callable(needed_type.type):
                                    pass
                                elif needed_type.type.assign_type(spec[0]):
                                    at_least_one = True
                                    new_const = weave_internal.make_const_node(
                                        spec[0], spec[1]
                                    )
                                    new_possible_params.extend(
                                        [
                                            params + [new_const]
                                            for params in all_possible_params
                                        ]
                                    )
                            if not at_least_one:
                                print(
                                    f"Skipping op {op} because it needs {needed_type.type} for {needed_type.name} but we have no specs for it"
                                )
                                break
                            all_possible_params = new_possible_params
                        else:
                            root_added = True
                            for param_set in all_possible_params:
                                params = {
                                    all_named_args[i].name: param_set[i]
                                    for i in range(len(param_set))
                                }
                                working_list.append(op(**params))
            if not root_added:
                working_list.append(root)
        roots = working_list
    return roots
