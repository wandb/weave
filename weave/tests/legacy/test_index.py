import weave


def test_index():
    arr = weave.save([{"a": [1, 2], "i": 0}, {"a": [3, 4], "i": 1}])
    assert weave.use(arr.map(lambda x: x["a"][x["i"]])) == [1, 4]
