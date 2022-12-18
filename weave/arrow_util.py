import pyarrow as pa


##### Classes and methods for working with arrow Types


class ArrowTypeWithFieldInfo:
    def __init__(self, type_, nullable, metadata):
        self.type = type_
        self.nullable = nullable
        self.metadata = metadata


def arrow_type_with_metadata(type_, metadata):
    if isinstance(type_, ArrowTypeWithFieldInfo):
        # blow away existing
        type_.metadata = metadata
    else:
        return ArrowTypeWithFieldInfo(type_, False, metadata)


def arrow_type_with_nullable(type_):
    if isinstance(type_, ArrowTypeWithFieldInfo):
        type_.nullable = True
    else:
        return ArrowTypeWithFieldInfo(type_, True, None)


def arrow_field(name, type_):
    if isinstance(type_, ArrowTypeWithFieldInfo):
        return pa.field(
            name, type_.type, nullable=type_.nullable, metadata=type_.metadata
        )
    return pa.field(name, type_)


def arrow_type(type_):
    if isinstance(type_, ArrowTypeWithFieldInfo):
        return type_.type
    return type_
