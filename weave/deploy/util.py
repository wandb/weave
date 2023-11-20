import json
import os
import re
import subprocess
import sys
import typing


def execute(
    args: list[str],
    timeout: typing.Optional[float] = None,
    cwd: typing.Optional[str] = None,
    env: typing.Optional[dict[str, str]] = None,
    input: typing.Optional[str] = None,
    capture: bool = True,
) -> typing.Any:
    process = subprocess.Popen(
        args,
        stdout=subprocess.PIPE if capture else sys.stdout,
        stderr=subprocess.PIPE if capture else sys.stderr,
        stdin=subprocess.PIPE if capture else sys.stdin,
        universal_newlines=True,
        env=env or os.environ.copy(),
        cwd=cwd,
    )
    out, err = process.communicate(timeout=timeout, input=input)
    if process.returncode != 0:
        raise ValueError(f"Command failed: {err or ''}")

    if not capture:
        return None

    try:
        return json.loads(out)
    except json.JSONDecodeError:
        raise ValueError(f"Failed to parse JSON from command: {out}")


def safe_name(name: str) -> str:
    """The name must use only lowercase alphanumeric characters and dashes,
    cannot begin or end with a dash, and cannot be longer than 63 characters."""
    fixed_name = re.sub(r"[^a-z0-9-]", "-", name.lower()).strip("-")
    if len(fixed_name) == 0:
        return "weave-op"
    elif len(fixed_name) > 63:
        return fixed_name[:63]
    else:
        return fixed_name
