from ..api import op, mutation, weave_class
from .. import weave_types as types


@op(name="root-string")
def string(v: str) -> str:
    return v


@op(name="string-lastLetter")
def lastLetter(v: str) -> str:
    return v[-1]


@weave_class(weave_type=types.String)
class String:
    @op(
        name="string-set",
        input_type={"self": types.String(), "val": types.String()},
        output_type=types.String(),
    )
    @mutation
    def set(self, val):
        return val

    @op(name="string-equal")
    def __eq__(lhs: str, rhs: str) -> bool:  # type: ignore
        return lhs == rhs

    @op(name="string-notEqual")
    def __ne__(lhs: str, rhs: str) -> bool:  # type: ignore
        return lhs != rhs

    @op(name="string-contains")
    def __contains__(str: str, sub: str) -> bool:  # type: ignore
        return sub in str

    @op(name="string-in")
    def in_(lhs: str, rhs: str) -> bool:  # type: ignore
        return lhs in rhs

    @op(name="string-add")
    def __add__(lhs: str, rhs: str) -> str:  # type: ignore
        return lhs + rhs

    @op(name="string-len")
    def len(str: str) -> int:  # type: ignore
        return len(str)

    @op(name="string-append")
    def append(str: str, suffix: str) -> str:  # type: ignore
        return str + suffix

    @op(name="string-prepend")
    def prepend(str: str, prefix: str) -> str:  # type: ignore
        return prefix + str

    @op(name="string-split")
    def split(str: str, sep: str) -> list[str]:  # type: ignore
        return str.split(sep)

    @op(name="string-partition")
    def partition(str: str, sep: str) -> list[str]:  # type: ignore
        return list(str.partition(sep))

    @op(name="string-startsWith")
    def startswith(str: str, prefix: str) -> bool:  # type: ignore
        return str.startswith(prefix)

    @op(name="string-endsWith")
    def endswith(str: str, suffix: str) -> bool:  # type: ignore
        return str.endswith(suffix)

    @op(name="string-isAlpha")
    def isalpha(str: str) -> bool:  # type: ignore
        return str.isalpha()

    @op(name="string-isNumeric")
    def isnumeric(str: str) -> bool:  # type: ignore
        return str.isnumeric()

    @op(name="string-isAlnum")
    def isalnum(str: str) -> bool:  # type: ignore
        return str.isalnum()

    @op(name="string-lower")
    def lower(str: str) -> str:  # type: ignore
        return str.lower()

    @op(name="string-upper")
    def upper(str: str) -> str:  # type: ignore
        return str.upper()

    @op(name="string-slice")
    def slice(str: str, begin: int, end: int) -> str:  # type: ignore
        return str[begin:end]

    @op(name="string-replace")
    def replace(str: str, sub: str, newSub: str) -> str:  # type: ignore
        return str.replace(sub, newSub)

    # @op(name="string-findAll")
    # def findAll(str: str, sub: str) -> list[int]:  # type: ignore
    #     return str.find(sub)

    @op(name="string-strip")
    def strip(str: str) -> str:  # type: ignore
        return str.strip()

    @op(name="string-lStrip")
    def lstrip(str: str) -> str:  # type: ignore
        return str.lstrip()

    @op(name="string-rStrip")
    def rstrip(str: str) -> str:  # type: ignore
        return str.rstrip()


types.String.instance_class = String
