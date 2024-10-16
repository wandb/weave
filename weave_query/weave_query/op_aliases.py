_OP_ALIASES: list[list[str]] = [
    ["__add__", "add"],
    ["__sub__", "sub"],
    ["__mul__", "mult"],
    ["__truediv__", "div"],
    ["__neg__", "negate"],
    ["__pow__", "powBinary"],
    ["__mod__", "modulo"],
    ["__round__", "round"],
    ["__getitem__", "pick", "index"],
    ["__contains__", "contains"],
    ["__len__", "count"],
    ["__ge__", "greaterEqual"],
    ["__gt__", "greater"],
    ["__le__", "lessEqual"],
    ["__lt__", "less"],
    ["__eq__", "equal"],
    ["__ne__", "notEqual"],
    ["startswith", "startsWith"],
    ["endswith", "endsWith"],
    ["isalpha", "isAlpha"],
    ["isalnum", "isAlnum"],
    ["isnumeric", "isNumeric"],
    ["lstrip", "lStrip"],
    ["rstrip", "rStrip"],
    ["in_", "in"],
    # This is Run.set_state. TODO: just fix it.
    ["set_state", "setstate"],
    ["set_output", "setoutput"],
    ["print_", "print"],
    ["await_final_output", "await"],
]

_OP_ALIASES_LOOKUP: dict[str, list[str]] = {}
for alias_set in _OP_ALIASES:
    for op in alias_set:
        _OP_ALIASES_LOOKUP[op] = alias_set


def get_op_aliases(op_name: str) -> list[str]:
    return _OP_ALIASES_LOOKUP.get(op_name, [op_name])
