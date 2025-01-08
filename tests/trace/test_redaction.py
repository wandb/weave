import weave


def test_code_capture_redacts_sensitive_values(client):
    api_key = "123"

    @weave.op
    def func(x: int) -> int:
        cap = api_key
        return x + 1

    ref = weave.publish(func)
    op = ref.get()

    captured_code = op.get_captured_code()

    assert 'api_key = "REDACTED"' in captured_code
