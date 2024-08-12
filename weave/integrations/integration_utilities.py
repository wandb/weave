import re

MAX_RUN_NAME_LENGTH = 128


def make_pythonic_function_name(name: str) -> str:
    name = name.replace("<", "_").replace(">", "")

    valid_run_name = re.sub(r"[^a-zA-Z0-9 .\\-_]", "_", name)
    return valid_run_name


def truncate_op_name(name: str) -> str:
    if len(name) <= MAX_RUN_NAME_LENGTH:
        return name

    trim_amount_needed = len(name) - MAX_RUN_NAME_LENGTH
    parts = name.split(".")
    last_part = parts[-1]

    if len(last_part) <= trim_amount_needed + 1:
        # In this case, the last part is shorter than the amount we need to trim.
        raise ValueError("Unable to create a valid run name from: " + name)

    last_part = last_part[:-trim_amount_needed]
    parts[-1] = last_part
    name = ".".join(parts)
    return name
