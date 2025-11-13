from weave.trace_server.client_server_common.digest_builder import (
    ref_stable_json_digest,
)


def test_ref_stable_json_digest():
    basic_data = {"a": 1, "b": 2}
    basic_data_digest = ref_stable_json_digest(basic_data)
    object_with_ext_ref = {
        "ref_to_thing": f"weave:///entity/project/object/my_thing:{basic_data_digest}"
    }
    object_with_ext_ref_digest = ref_stable_json_digest(object_with_ext_ref)

    object_with_int_ref = {
        "ref_to_thing": f"weave-trace-internal:///project_id/object/my_thing:{basic_data_digest}"
    }
    object_with_int_ref_digest = ref_stable_json_digest(object_with_int_ref)

    assert object_with_ext_ref_digest == object_with_int_ref_digest
