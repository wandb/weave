import pyarrow as pa
from collections.abc import Iterable


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


##### Arrow adapters


class ArrowTableList(Iterable):
    def __init__(self, arrow_table, mapper, artifact):
        self._arrow_table = arrow_table
        self._artifact = artifact
        self._deserializer = mapper

    def __getitem__(self, index):
        if index >= self._arrow_table.num_rows:
            return None
        # Very inefficient, we always read the whole row!
        # TODO: We need to make this column access lazy. But we also want
        #     vectorize access generally, which probably happens in a compile
        #     pass. Need to think about it.
        row_dict = {}
        for column in self._arrow_table.column_names:
            row_dict[column] = self._arrow_table.column(column)[index].as_py()
        return self._deserializer.apply(row_dict)

    def __iter__(self):
        for i in range(len(self)):
            yield self[i]

    def __len__(self):
        return self._arrow_table.num_rows

    def __eq__(self, other):
        if len(self) != len(other):
            return False
        for x, y in zip(iter(self), iter(other)):
            if x != y:
                return False
        return True


class ArrowArrayList(Iterable):
    def __init__(self, arrow_array):
        self._arrow_array = arrow_array

    def __getitem__(self, index):
        if index >= len(self._arrow_array):
            return None
        return self._arrow_array[index].as_py()

    def __iter__(self):
        for i in range(len(self)):
            yield self[i]

    def __eq__(self, other):
        if len(self) != len(other):
            return False
        for s, o in zip(self, other):
            if s != o:
                return False
        return True

    def __len__(self):
        return len(self._arrow_array)
