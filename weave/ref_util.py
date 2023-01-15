import typing


def parse_local_ref_str(s: str) -> typing.Tuple[str, typing.Optional[list[str]]]:
    if "#" not in s:
        return s, None
    path, extra = s.split("#", 1)
    return path, extra.split("/")
