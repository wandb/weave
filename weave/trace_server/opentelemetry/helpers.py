import re

# TODO: Move shared helpers into this file
# This logic doesn't really belong in any existing files, but there is logic in existing files that belongs here.


def capture_parts(
    s: str, delimiters: list[str] = [",", ";", "|", " ", "/", "?", "."]
) -> list[str]:
    """Split a string on multiple delimiters while preserving the delimiters in the result.

    This function splits a string using the specified delimiters and includes those
    delimiters in the resulting list. Empty strings are filtered out from the result.

    Args:
        s: The input string to split.
        delimiters: A list of delimiter strings to split on. Defaults to common delimiters.

    Returns:
        A list containing the parts of the split string, including the delimiters.
        If no splits occurred, returns the original string in a list.

    Example:
        >>> capture_parts("hello/world.txt")
        ['hello', '/', 'world', '.', 'txt']
    """
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


def shorten_name(
    name: str, max_len: int, abbrv: str = "...", use_delimiter_in_abbr: bool = True
) -> str:
    """Shorten a string to a maximum length by intelligently abbreviating at delimiters.

    This function shortens a string to fit within a specified maximum length.
    It tries to shorten at natural break points (delimiters) rather than
    arbitrarily truncating in the middle of words.

    Args:
        name: The input string to shorten.
        max_len: The maximum allowed length of the output string.
        abbrv: The abbreviation string to append when shortening (default "...").
        use_delimiter_in_abbr: If True, includes the delimiter before the abbreviation
                              when shortening at a delimiter (default True).

    Returns:
        A shortened version of the input string that doesn't exceed max_len characters.

    Examples:
        >>> shorten_name("hello/world.txt", 10)
        'hello/...'
        >>> shorten_name("hello/world.txt", 10, use_delimiter_in_abbr=False)
        'hello...'
        >>> shorten_name("hello/world.txt", 20)
        'hello/world.txt'
        >>> shorten_name("verylongword", 8)
        'verylo...'
        >>> shorten_name("hello/world.txt", 10, ":1234" use_delimiter_in_abbr=False)
        'hello:1234'
    """
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
        elif abbrv.startswith(next_delimiter) or not use_delimiter_in_abbr:
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
