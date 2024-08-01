import weave


def test_non_standard_object_naming(client):
    column_name = "column with crazy characters !@#$%^&*()/\/:"
    dataset = weave.Dataset(
        name=":/!@#$%^ &*():/\/",
        rows=[
            {
                column_name: "value",
            }
        ],
    )
    weave.publish(dataset)

    deep_val = dataset.rows[0][column_name]
    assert deep_val == "value"
    ref = deep_val.ref
    assert ref.uri == "weave:///dataset/{dataset.id}/object/{column_name}:value"
    gotten_val = weave.get(ref)
    assert gotten_val == deep_val
