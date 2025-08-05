from collections import defaultdict

import weave
from weave.trace.api import get_current_call
from weave.trace_server import trace_server_interface as tsi


def test_trace_call_query_filter_ancestor_ids(client):
    descendant_sets = defaultdict(set)

    def add_descendants(ancestor_id, descendant_id):
        descendant_sets[ancestor_id].add(descendant_id)
        for descendant in descendant_sets[descendant_id]:
            add_descendants(ancestor_id, descendant)

    def call_op(op):
        _, call = op.call()
        current_call = get_current_call()
        if current_call is not None:
            add_descendants(current_call.id, call.id)

    @weave.op
    def leaf_op_1():
        pass

    @weave.op
    def leaf_op_2():
        pass

    @weave.op
    def middle_op_1():
        call_op(leaf_op_1)
        call_op(leaf_op_2)

    @weave.op
    def middle_op_2():
        call_op(leaf_op_1)
        call_op(leaf_op_2)

    @weave.op
    def root_op():
        call_op(middle_op_1)
        call_op(middle_op_2)

    root_op()
    root_op()

    no_ancestor_examples = [([], [])]
    single_ancestor_examples = [
        ([call_id], descendant_sets[call_id]) for call_id in descendant_sets.keys()
    ]

    for ancestor_ids, exp_ids in [
        *no_ancestor_examples,
        *single_ancestor_examples,
    ]:
        inner_res = client.server.calls_query(
            tsi.CallsQueryReq(
                project_id=client._project_id(),
                filter=tsi.CallsFilter(ancestor_ids=ancestor_ids),
            )
        )
        found_ids = set(call.id for call in inner_res.calls)

        assert found_ids == exp_ids
