import re

# TODO: Move shared helpers into this file
# This logic doesn't really belong in any existing files, but there is logic in existing files that belongs here.


def capture_parts(
    s: str, delimiters: list[str] = [",", ";", "|", " ", "/", "?", "."]
) -> list[str]:
    # Split a string based on multiple patterns, including the split characters in the result.

    # Escape special regex characters and join with | for regex alternation
    capture = "|".join(map(re.escape, delimiters))
    pattern = f"({(capture)})"

    # Use re.split with capturing groups to include the delimiters
    parts = re.split(pattern, s)

    # Filter out empty strings that might result from the split
    result = [part for part in parts if part != ""]

    result = list(filter(lambda x: len(x) > 0, parts))
    # If no split occurred, return the original string in a list
    if len(result) == 0:
        return [s]

    return result


def shorten_name(name: str, max_len: int, abbrv: str = "...") -> str:
    # Split the string based on all of the listed delimiters
    parts = capture_parts(name)
    if len(parts) <= 1:
        # No delimiters found, just truncate
        return name[: max_len - (len(abbrv))] + abbrv

    shortened_name = parts[0]

    # If the first part is already longer than max_len, truncate it
    if len(shortened_name) > max_len - len(abbrv):
        return shortened_name[: max_len - len(abbrv)] + abbrv

    # We already have the first part in shortened_name, so skip it
    for i in range(1, len(parts) - 1, 2):
        # Concatenate the delimiter with the next part
        next_delimiter = parts[i]
        next_part = f"{next_delimiter}{parts[i+1]}"
        if len(shortened_name) + len(next_part) > max_len - (len(abbrv) + 1):
            shortened_name += f"{next_delimiter}{abbrv}"
            break
        shortened_name += next_part

    return shortened_name
