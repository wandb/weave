import hashlib
import json
import typing
import uuid

from . import trace_server_interface as tsi


# This is a quick solution but needs more thought


def generate_id() -> str:
    return str(uuid.uuid4())


def version_hash_for_object(obj: tsi.PartialObjForCreationSchema) -> str:
    type_dict = _order_dict(obj.type_dict)
    # val_dict = _order_dict(obj.val_dict)

    hasher = hashlib.md5()

    hasher.update(json.dumps(type_dict).encode())
    # hasher.update(json.dumps(val_dict).encode())

    files = _order_dict(obj.encoded_file_map or {})
    for k, v in files.items():
        hasher.update(k.encode())
        if isinstance(v, str):
            hasher.update(v.encode())
        elif isinstance(v, bytes):
            hasher.update(v)
        else:
            raise ValueError(f"Unexpected type for file {k}: {type(v)}")

    return hasher.hexdigest()


# def version_hash_for_op(op: tsi.PartialOpForCreationSchema) -> str:

#     hasher = hashlib.md5()
#     hasher.update(op.name.encode())
#     if op.code:
#         hasher.update(op.code.encode())
#     if op.environment_state_identity:
#         hasher.update(op.environment_state_identity.encode())

#     return hasher.hexdigest()


def _decode_bytes_to_str(dictionary):
    return {
        k: _decode_bytes_to_str(v)
        if isinstance(v, dict)
        else v.decode()
        if isinstance(v, bytes)
        else v
        for k, v in dictionary.items()
    }


def _order_dict(dictionary):
    return {
        k: _order_dict(v) if isinstance(v, dict) else v
        for k, v in sorted(dictionary.items())
    }


def prepare_files_map_for_transport(
    encoded_file_map: typing.Optional[typing.Dict[str, bytes]] = None
) -> typing.Dict[str, typing.Tuple[int, int]]:
    encoded_file_map_as_length_and_big_int = {}
    file_map = encoded_file_map or {}
    for k, v in file_map.items():
        encoded_file_map_as_length_and_big_int[k] = (len(v), int.from_bytes(v, "big"))
    return encoded_file_map_as_length_and_big_int


def read_transport_files_map(
    encoded_file_map_as_length_and_big_int: typing.Dict[str, typing.Tuple[int, int]]
) -> typing.Dict[str, bytes]:
    encoded_file_map = {}
    for k, (length, big_int) in encoded_file_map_as_length_and_big_int.items():
        encoded_file_map[k] = big_int.to_bytes(length, "big")
    return encoded_file_map


def prepare_partial_obj_for_creation_schema_for_transport(
    partial: tsi.PartialObjForCreationSchema,
) -> tsi.TransportablePartialObjForCreationSchema:
    partial_dict = partial.model_dump()
    partial_dict[
        "encoded_file_map_as_length_and_big_int"
    ] = prepare_files_map_for_transport(partial.encoded_file_map)
    partial_dict["encoded_file_map"] = None
    return tsi.TransportablePartialObjForCreationSchema.parse_obj(partial_dict)


def read_partial_obj_for_creation_schema_from_transport(
    transported: tsi.TransportablePartialObjForCreationSchema,
) -> tsi.PartialObjForCreationSchema:
    transported_dict = transported.model_dump()
    transported_dict["encoded_file_map"] = read_transport_files_map(
        transported.encoded_file_map_as_length_and_big_int
    )
    transported_dict.pop("encoded_file_map_as_length_and_big_int")
    return tsi.PartialObjForCreationSchema.parse_obj(transported_dict)


def prepare_obj_schema_for_transport(
    partial: tsi.ObjSchema,
) -> tsi.TransportableObjSchema:
    partial_dict = partial.model_dump()
    partial_dict[
        "encoded_file_map_as_length_and_big_int"
    ] = prepare_files_map_for_transport(partial.encoded_file_map)
    partial_dict["encoded_file_map"] = {}
    return tsi.TransportableObjSchema.parse_obj(partial_dict)


def read_obj_schema_from_transport(
    transported: tsi.TransportableObjSchema,
) -> tsi.TransportableObjSchema:
    transported_dict = transported.model_dump()
    transported_dict["encoded_file_map"] = read_transport_files_map(
        transported.encoded_file_map_as_length_and_big_int
    )
    transported_dict.pop("encoded_file_map_as_length_and_big_int")
    return tsi.TransportableObjSchema.parse_obj(transported_dict)
