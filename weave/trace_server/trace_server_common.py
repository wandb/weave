import typing


def make_nested_dict(parts: list[str], val: typing.Any) -> typing.Any:
    if len(parts) == 1:
        return val
    return {parts[0]: make_nested_dict(parts[1:], val)}
