import typing
from ..api import op, weave_class
from .. import weave_types as types
import re
import json
import numpy as np


@op(name="root-string")
def string(v: str) -> str:
    return v


@op(name="string-lastLetter")
def lastLetter(v: str) -> str:
    return v[-1]


def _json_parse(string: str) -> typing.Any:
    return json.loads(string)


@weave_class(weave_type=types.String)
class String:
    @op(
        name="string-_set",
        input_type={"self": types.String(), "val": types.String()},
        output_type=types.String(),
    )
    def set(self, val):
        return val

    @op(name="string-equal")
    def __eq__(lhs: typing.Optional[str], rhs: typing.Optional[str]) -> bool:  # type: ignore[misc]
        return lhs == rhs

    @op(name="string-notEqual")
    def __ne__(lhs: typing.Optional[str], rhs: typing.Optional[str]) -> bool:  # type: ignore[misc]
        return lhs != rhs

    @op(name="string-contains")
    def __contains__(str: str, sub: str) -> bool:  # type: ignore[misc]
        return sub in str

    @op(name="string-in")
    def in_(lhs: str, rhs: typing.Optional[str]) -> bool:  # type: ignore[misc]
        rhs = rhs or ""
        return lhs in rhs

    @op(name="string-add")
    def __add__(lhs: str, rhs: typing.Optional[str]) -> str:  # type: ignore[misc]
        if rhs == None:
            return None  # type: ignore
        return lhs + rhs  # type: ignore

    @op(name="string-len")
    def len(str: str) -> int:  # type: ignore[misc]
        return len(str)

    @op(name="string-append")
    def append(str: str, suffix: typing.Optional[str]) -> str:  # type: ignore[misc]
        suffix = suffix or ""
        return str + suffix

    @op(name="string-prepend")
    def prepend(str: str, prefix: typing.Optional[str]) -> str:  # type: ignore[misc]
        prefix = prefix or ""
        return prefix + str

    @op(name="string-split")
    def split(str: str, sep: typing.Optional[str]) -> list[str]:  # type: ignore[misc]
        if sep is None:
            return list(str)
        return str.split(sep)

    @op(name="string-partition")
    def partition(str: str, sep: typing.Optional[str]) -> list[str]:  # type: ignore[misc]
        if sep is None:
            return [str, "", ""]
        return list(str.partition(sep))

    @op(name="string-startsWith")
    def startswith(str: str, prefix: typing.Optional[str]) -> bool:  # type: ignore[misc]
        prefix = prefix or ""
        return str.startswith(prefix)

    @op(name="string-endsWith")
    def endswith(str: str, suffix: typing.Optional[str]) -> bool:  # type: ignore[misc]
        suffix = suffix or ""
        return str.endswith(suffix)

    @op(name="string-isAlpha")
    def isalpha(str: str) -> bool:  # type: ignore[misc]
        return str.isalpha()

    @op(name="string-isNumeric")
    def isnumeric(str: str) -> bool:  # type: ignore[misc]
        # custom logic to match JS
        if str == "":
            return False
        if str[0] == "-":
            str = str[1:]
        if str == "":
            return False
        if str[0] == ".":
            str = str[1:]
            if "." in str:
                return False
        if str == "":
            return False
        if str[-1] == ".":
            str = str[:-1]
            if "." in str:
                return False
        if str == "":
            return False
        parts = str.split(".")
        if len(parts) > 2:
            return False
        for part in parts:
            if not part.isnumeric():
                return False
        return True

    @op(name="string-isAlnum")
    def isalnum(str: str) -> bool:  # type: ignore[misc]
        return str.isalnum()

    @op(name="string-lower")
    def lower(str: str) -> str:  # type: ignore[misc]
        return str.lower()

    @op(name="string-upper")
    def upper(str: str) -> str:  # type: ignore[misc]
        return str.upper()

    @op(name="string-slice")
    def slice(  # type: ignore[misc]
        str: str, begin: typing.Union[int, None], end: typing.Union[int, None] = None
    ) -> str:
        begin = 0 if begin is None else begin
        end = len(str) if end is None else end
        return str[begin:end]

    @op(name="string-replace")
    def replace(  # type: ignore[misc]
        str: str, sub: typing.Union[str, None], newSub: typing.Union[str, None]
    ) -> str:
        if sub is None:
            return str
        newSub = newSub or ""
        return str.replace(sub, newSub)

    @op(name="string-findAll")
    def findall(str: str, sub: typing.Union[str, None]) -> list[str]:  # type: ignore[misc]
        if sub is None:
            return []
        return [g[0] if isinstance(g, list) else g for g in re.findall(sub, str)]

    @op(name="string-strip")
    def strip(str: str) -> str:  # type: ignore[misc]
        return str.strip()

    @op(name="string-lStrip")
    def lstrip(str: str) -> str:  # type: ignore[misc]
        return str.lstrip()

    @op(name="string-rStrip")
    def rstrip(str: str) -> str:  # type: ignore[misc]
        return str.rstrip()

    @op()
    def format(
        self, named_items: dict[str, typing.Optional[typing.Union[str, int]]]
    ) -> str:
        return self.format(**named_items)

    @op(hidden=True)
    def json_parse_refine(self) -> types.Type:
        return types.TypeRegistry.type_of(_json_parse(self))  # type: ignore

    @op(refine_output_type=json_parse_refine)
    def json_parse(self) -> typing.Any:
        return _json_parse(self)  # type: ignore

    # I'd prefer json_parse(s, Type), or json_parse(s).cast(Type), but
    # for now this is easy. We know the output type is list at call time
    # so ops are dispatchable. And then we refine to get the full type.
    @op(refine_output_type=json_parse_refine)
    def json_parse_list(self) -> list[typing.Any]:
        res = _json_parse(self)  # type: ignore
        if not isinstance(res, list):
            raise ValueError("Expected a list")
        return res

    @op(name="string-toNumber", output_type=types.optional(types.Number()))
    def to_number(self):
        if self.isnumeric():
            return float(self)  # type: ignore
        return None


types.String.instance_class = String


@op(name="string-levenshtein", render_info={"type": "function"})
def levenshtein(str1: typing.Union[str, None], str2: typing.Union[str, None]) -> int:
    return _levenshtein(str1 or "", str2 or "")


def _levenshtein(str1: str, str2: str) -> int:
    """calculate the number of single-character edits between str1 and str2"""
    if len(str1) < len(str2):
        return _levenshtein(str2, str1)

    if len(str2) == 0:
        return len(str1)

    arr1 = np.array(tuple(str1))
    arr2 = np.array(tuple(str2))

    previous_row = np.arange(arr2.size + 1)
    for s in arr1:
        current_row = previous_row + 1
        current_row[1:] = np.minimum(
            current_row[1:],
            np.add(previous_row[:-1], arr2 != s),
        )
        current_row[1:] = np.minimum(
            current_row[1:],
            current_row[0:-1] + 1,
        )
        previous_row = current_row

    return previous_row[-1].item()
