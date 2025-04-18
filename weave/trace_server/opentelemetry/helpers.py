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
    if len(name) <= max_len:
        return name
    # Split the string based on all of the listed delimiters
    delimiters = [",", ";", "|", " ", "/", "?", "."]
    parts = capture_parts(name, delimiters)
    abbrv_len = len(abbrv)
    if len(parts) <= 1:
        # No delimiters found, just truncate
        return name[: max_len - abbrv_len] + abbrv

    shortened_name = parts[0]

    # If the first part is already longer than max_len, truncate it
    if len(shortened_name) > max_len - abbrv_len:
        return shortened_name[: max_len - abbrv_len] + abbrv

    i = 1
    while i < len(parts):
        # Concatenate the delimiter with the next part
        next_delimiter = ""
        while parts[i] in delimiters:
            next_delimiter = next_delimiter + parts[i]
            i += 1

        next_part = f"{next_delimiter}{parts[i]}"
        # If there is no abbreviation, do not end on a delimiter (ex. no trailing periods)
        if not abbrv_len:
            delimiter_with_abbrv = ""
        elif abbrv.startswith(next_delimiter):
            delimiter_with_abbrv = abbrv
        else:
            delimiter_with_abbrv = f"{next_delimiter}{abbrv}"

        if len(shortened_name) + len(next_part) >= max_len - (
            len(delimiter_with_abbrv)
        ):
            shortened_name += delimiter_with_abbrv
            break
        else:
            shortened_name += next_part
        i += 1
    return shortened_name
