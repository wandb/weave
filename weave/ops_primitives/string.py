import typing
from ..api import op, mutation, weave_class
from .. import weave_types as types
import Levenshtein
import re


@op(name="root-string")
def string(v: str) -> str:
    return v


@op(name="string-lastLetter")
def lastLetter(v: str) -> str:
    return v[-1]


@weave_class(weave_type=types.String)
class String:
    @op(
        name="string-_set",
        input_type={"self": types.String(), "val": types.String()},
        output_type=types.String(),
    )
    @mutation
    def set(self, val):
        return val

    @op(name="string-equal")
    def __eq__(lhs: str, rhs: str) -> bool:  # type: ignore[misc]
        return lhs == rhs

    @op(name="string-notEqual")
    def __ne__(lhs: str, rhs: str) -> bool:  # type: ignore[misc]
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
        rhs = rhs or ""
        return lhs + rhs

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


types.String.instance_class = String


@op(name="string-levenshtein", render_info={"type": "function"})
def levenshtein(str1: typing.Union[str, None], str2: typing.Union[str, None]) -> int:
    return Levenshtein.distance(str1 or "", str2 or "")
