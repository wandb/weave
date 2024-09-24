import weave
from weave.trace.weave_client import WeaveClient
from weave.type_serializers.JSONBlob.jsonblob import JSONBlob


def test_log_large_object(client: WeaveClient) -> None:
    data = {f"key_{i}": f"value_{i}" for i in range(50_000)}

    @weave.op
    def log_large_object_dict_value() -> dict:
        return {"blob": data}

    @weave.op
    def log_large_object_dict_value_input(in_data: dict) -> dict:
        return {}

    @weave.op
    def log_large_object_raw() -> dict:
        return data

    @weave.op
    def log_large_object_list_value() -> list:
        return [data]

    @weave.op
    def log_large_object_tuple() -> tuple:
        return (data,)

    log_large_object_dict_value()
    call = list(log_large_object_dict_value.calls())[0]
    assert isinstance(call.output["blob"], JSONBlob)
    assert call.output["blob"].obj == data

    log_large_object_dict_value_input(data)
    call = list(log_large_object_dict_value_input.calls())[0]
    assert isinstance(call.inputs["in_data"], JSONBlob)
    assert call.inputs["in_data"].obj == data

    log_large_object_raw()
    call = list(log_large_object_raw.calls())[0]
    assert isinstance(call.output, JSONBlob)
    assert call.output.obj == data

    log_large_object_list_value()
    call = list(log_large_object_list_value.calls())[0]
    assert isinstance(call.output[0], JSONBlob)
    assert call.output[0].obj == data

    log_large_object_tuple()
    call = list(log_large_object_tuple.calls())[0]
    assert isinstance(call.output[0], JSONBlob)
    assert call.output[0].obj == data
