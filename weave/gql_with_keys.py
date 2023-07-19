import json
import typing

from dataclasses import dataclass
from . import weave_types as types
from . import artifact_fs


T = typing.TypeVar("T", bound="GQLTypeMixin")


@dataclass
class GQLTypeMixin:
    gql: dict

    @classmethod
    def from_gql(cls: typing.Type[T], gql_dict: dict) -> T:
        return cls(gql=gql_dict)


class GQLClassWithKeysType(types.Type):
    # Has no instance classes or instance class - type of is performed in
    # original weave type

    keyless_weave_type_class: typing.Type[types.Type]
    keys: dict[str, types.Type]

    def __init__(
        self,
        keyless_weave_type_class: typing.Type[types.Type],
        keys: dict[str, types.Type],
    ):
        self.keyless_weave_type_class = keyless_weave_type_class
        self.keys = keys

    @property
    def _assignment_form(self) -> types.Type:
        return self.keyless_weave_type_class()

    def _assign_type_inner(self, other_type: types.Type) -> bool:
        # TODO: think more about how this will work with tags - might need to be modified
        return (
            isinstance(other_type, GQLClassWithKeysType)
            and self.keyless_weave_type_class == other_type.keyless_weave_type_class
            and self.keys == other_type.keys
        )

    def _str_repr(self) -> str:
        keys_repr = dict(sorted([(k, v.__repr__()) for k, v in self.keys.items()]))
        return f"{self.keyless_weave_type_class.__name__}WithKeys({keys_repr})"

    def __repr__(self) -> str:
        return self._str_repr()

    def _to_dict(self) -> dict:
        property_types = {}
        for key, type_ in self.keys.items():
            property_types[key] = type_.to_dict()
        result = {
            "keys": property_types,
            "keyless_weave_type_class": self.keyless_weave_type_class().to_dict(),
        }
        return result

    @classmethod
    def from_dict(cls, d: dict) -> "GQLClassWithKeysType":
        property_types = {}
        for key, type_ in d["keys"].items():
            property_types[key] = types.TypeRegistry.type_from_dict(type_)
        keyless_weave_type_class = types.TypeRegistry.type_from_dict(
            d["keyless_weave_type_class"]
        ).__class__

        return cls(keyless_weave_type_class, property_types)

    def save_instance(
        self, obj: GQLTypeMixin, artifact: artifact_fs.FilesystemArtifact, name: str
    ) -> None:
        from . import mappers_python

        serializer = mappers_python.map_to_python(self, artifact)
        result = serializer.apply(obj)
        with artifact.new_file(
            f"{name}.{self.keyless_weave_type_class.__name__}WithKeys.json"
        ) as f:
            json.dump(result, f, allow_nan=False)

    def load_instance(
        self,
        artifact: artifact_fs.FilesystemArtifact,
        name: str,
        extra: typing.Optional[list] = None,
    ) -> GQLTypeMixin:
        from . import mappers_python

        with artifact.open(
            f"{name}.{self.keyless_weave_type_class.__class__.__name__}WithKeys.json"
        ) as f:
            result = json.load(f)
        mapper = mappers_python.map_from_python(self, artifact)
        mapped_result = mapper.apply(result)
        if extra is not None:
            return mapped_result[extra[0]]
        return typing.cast(GQLTypeMixin, mapped_result)
