"""
In order to effectively query/join traces, we need to operate on inputs. However, inputs
are often large and complex - reading that column is usually the worst part of a query.

`input_digests` is a new dictionary living under `attributes.weave` that contains a
digest of each input parameter for a given call.

The key thing here is that digests are stable across names / refs.
"""

import weave


def test_basic_input_digests(client):
    @weave.op
    def op_with_2_params(a: int, b: int):
        return a + b

    res = op_with_2_params(a=1, b=2)
    calls = client.get_calls()
    assert len(calls) == 1
    print(calls[0].attributes)
    assert calls[0].inputs == {"a": 1, "b": 2}
    assert calls[0].attributes["weave"]["input_digests"] == {
        "a": "a4aycY80YOGda4BOY1oYV0etpOqiLx1JwB5S3beHW0s",
        "b": "1HNeOiZeFu7gP1lxi5tdAwGcB9i2xRXQ2jpmbuwTqzU",
    }


def test_table_row_stability(client):
    @weave.op
    def op_with_dict_input(d: dict):
        return d["a"] + d["b"]

    row_a_digest = "2El9nYJ3CnBykmEJWqmPfvUVTXr0mfgDe2yiUClnhaY"
    row_a = {"a": 1, "b": 2}
    row_b = {"a": 3, "b": 4}

    res = op_with_dict_input(d=row_a)
    calls = client.get_calls()
    assert len(calls) == 1
    assert calls[0].inputs == {"d": row_a}
    assert calls[0].attributes["weave"]["input_digests"] == {"d": row_a_digest}

    # Now, create 2 datasets - each with their own digests, but both containing row_a
    dataset_a = weave.Dataset(rows=[row_a])
    dataset_b = weave.Dataset(rows=[row_b, row_a])

    published_dataset_a = weave.publish(dataset_a)
    published_dataset_b = weave.publish(dataset_b)

    gotten_dataset_a = weave.get(published_dataset_a)
    gotten_dataset_b = weave.get(published_dataset_b)

    # Here, the inputs would be a ref!
    res = op_with_dict_input(d=gotten_dataset_a[0])
    calls = client.get_calls()
    assert len(calls) == 2
    assert calls[1].inputs == {"d": row_a}
    # TODO: assert the ref
    assert calls[1].attributes["weave"]["input_digests"] == {"d": row_a_digest}

    # Here, the inputs would be a ref!
    res = op_with_dict_input(d=gotten_dataset_b[1])
    calls = client.get_calls()
    assert len(calls) == 3
    assert calls[2].inputs == {"d": row_a}
    # TODO: assert the ref
    assert calls[2].attributes["weave"]["input_digests"] == {"d": row_a_digest}
