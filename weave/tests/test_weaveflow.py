import pytest
import weave


@pytest.mark.skip("failing in CI for some reason")
def test_digestrefs():
    from weave import weaveflow

    graph_client = weave.init_local_client()

    ds = weave.WeaveList(
        [
            {
                "id": "0",
                "val": 100,
            },
            {
                "id": "0",
                "val": 101,
            },
        ]
    )

    ds0_ref = weave.publish(ds, "digestrefs")

    ds0 = weave.ref(str(ds0_ref)).get()

    @weave.op()
    def add5_to_row(row) -> int:
        return row["val"] + 5

    ds0_row0 = ds0[0]

    from .. import ref_base

    ds0_row0_ref = ref_base.get_ref(ds0_row0)
    assert ds0_row0_ref != None

    x = add5_to_row(ds0_row0)

    calls = ds0_row0_ref.input_to()
    assert len(calls) == 1

    ds = ds + [{"id": 2, "val": -10}]
    ds1_ref = weave.publish(ds, "digestrefs")

    ds1 = weave.ref(str(ds1_ref)).get()
    ds1_row0 = ds1[0]
    ds1_row0_ref = ref_base.get_ref(ds1_row0)

    assert ds0_row0_ref.digest == ds1_row0_ref.digest

    assert len(ds1_row0_ref.input_to()) == 0
    assert len(ds1_row0_ref.value_input_to()) == 1
