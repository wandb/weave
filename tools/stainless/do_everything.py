import subprocess
from pathlib import Path

from rich import print
from rich.live import Live
from rich.spinner import Spinner

base_path = Path(__file__).parent
root_path = base_path.parent.parent
services_path = root_path.parent.parent
print(f"Running from {base_path}")


def print_header(text: str):
    print(f"\n[blue bold]===>> {text} <<===[/blue bold]")


def with_spinner(text: str, func):
    spinner = Spinner("dots")
    with Live(spinner, refresh_per_second=10) as live:
        spinner.text = f" {text}..."
        result = func()
        live.stop()
    return result


print_header("Generating OpenAPI spec")
subprocess.run(
    [
        "python",
        base_path / "01_get_openapi_spec.py",
        services_path / "weave-trace",
    ],
    check=True,
)

print_header("Generating code")
subprocess.run(
    [
        "python",
        base_path / "02_generate_code.py",
    ],
    check=True,
)

print_header("Updating pyproject.toml")
subprocess.run(
    [
        "python",
        base_path / "03_update_pyproject.py",
        str(Path("~/repos/weave-stainless").expanduser()),
        "weave-trace",
    ],
    check=True,
)

print_header("Done, have a nice day :)")
