# Put this code in the top of assign_type in weave_types.py to log
# a bunch of types. Then use this test to test profile assignment.
#
# print("FROM TO", next_type, self)
# try:
#     open("/tmp/assigns.jsonl", "a").write(
#         "%s\n" % json.dumps({"from": next_type.to_dict(), "to": self.to_dict()})
#     )
# except TypeError:
#     pass


import cProfile
import json
import time

import pytest

import weave


def do_assigns(assigns):
    for assign_from, assign_to in assigns:
        assign_to.assign_type(assign_from)


@pytest.mark.skip("This is a performance test")
def test_assign_perf():
    assigns = []
    with open("./assigns.jsonl") as f:
        for line in f:
            parsed = json.loads(line)
            assigns.append(
                (
                    weave.types.TypeRegistry.type_from_dict(parsed["from"]),
                    weave.types.TypeRegistry.type_from_dict(parsed["to"]),
                )
            )
    start_time = time.time()
    with cProfile.Profile() as pr:
        for i in range(10):
            do_assigns(assigns)
    pr.dump_stats("assigns.prof")
    print("TIME", time.time() - start_time)
    print("LEN", len(assigns))
    assert 1 == 2
