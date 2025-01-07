import weave
from weave.trace import api


def redact_keys(d: dict) -> dict:
    for k in d:
        if "key" in k.lower():
            d[k] = "REDACTED"
    return d


def redact_output(s: str) -> str:
    if "key" in s.lower():
        return "API KEY DETECTED IN STRING; REDACTED."
    return s


# These globals are directly set here because we don't have a great way to test weave.init
api._global_postprocess_inputs = redact_keys
api._global_postprocess_output = redact_output


def test_global_postprocessing(client) -> None:
    @weave.op
    def func(api_key: str, secret_key: str, name: str, age: int) -> str:
        return (
            f"Hello, {name}! You are {age} years old.  Also your api_key is {api_key}."
        )

    res = func(api_key="123", secret_key="456", name="John", age=30)

    calls = list(client.get_calls())
    call = calls[0]

    assert call.inputs == {
        "api_key": "REDACTED",
        "secret_key": "REDACTED",
        "name": "John",
        "age": 30,
    }
    assert call.output == "API KEY DETECTED IN STRING; REDACTED."
