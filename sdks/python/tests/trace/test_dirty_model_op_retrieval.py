import weave


def test_dirty_model_op_retrieval(client):
    class MyModel(weave.Model):
        client: str

        @weave.op()
        def invoke(self):
            return self.client

    # Base Case
    m = MyModel(client="openai")
    assert m.invoke() == "openai"
    m.client = "anthropic"
    assert m.invoke() == "anthropic"

    # Case 1: Model is clean on first call
    m2 = weave.ref(m.ref.uri()).get()

    assert m2.invoke() == "openai"
    m2.client = "anthropic"
    assert m2.invoke() == "anthropic"

    # Case 2: Model is dirty on first call
    m3 = weave.ref(m.ref.uri()).get()
    m3.client = "anthropic"
    assert m3.invoke() == "anthropic"  # This fails in 0.51.8
    m3.client = "mistral"
    assert m3.invoke() == "mistral"
