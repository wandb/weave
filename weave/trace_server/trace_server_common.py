import typing


def _flatten_dict(
    d: dict[str, typing.Any], sep: str = ".", prefix: str = ""
) -> dict[str, typing.Any]:
    """
    Flatten a nested dict to a single-level dict, with keys in flattened notation.

    input: {"a": {"b": {"c": "d"}}}
    output: {"a.b.c": "d"}
    """
    if len(d) == 0 and prefix:
        return {prefix.removesuffix(sep): {}}

    flat = {}
    for key, val in d.items():
        if isinstance(val, dict):
            sub_dict = _flatten_dict(val, sep, f"{prefix}{key}{sep}")
            flat.update(sub_dict)
        else:
            flat[f"{prefix}{key}"] = val
    return flat


def _unflatten_dict(d: dict[str, typing.Any], sep: str = ".") -> dict[str, typing.Any]:
    """
    Unflatten a single-level dict to a nested dict.

    input: {"output.val.a": "a", "output.val.b": "b"}
    output: {"output": {"val": {"a": "a", "b": "b"}}}
    """
    out: typing.Dict[str, typing.Any] = {}
    for col, val in d.items():
        keys = col.split(sep)
        curr = out
        for key in keys[:-1]:
            curr = curr.setdefault(key, {})
        curr[keys[-1]] = val
    return out
