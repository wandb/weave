import weave

def test_dirty_model_op_retrieval(client):
    class MyModel(weave.Model):
        client: str

        @weave.op()
        def invoke(self):
            return self.client

    m = MyModel(client="openai")

    assert m.invoke() == "openai"

    m2 = weave.ref(m.ref.uri()).get()

    m2.client = "anthropic"

    assert m2.invoke() == "anthropic"

    