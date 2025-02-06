import subprocess
from pathlib import Path

base_path = Path(__file__).parent
root_path = base_path.parent.parent
services_path = root_path.parent.parent
print(f"Running from {base_path}")

subprocess.run(
    [
        "python",
        base_path / "01_get_openapi_spec.py",
        services_path / "weave-trace",
    ],
    check=True,
)
subprocess.run(
    [
        "python",
        base_path / "02_generate_code.py",
    ],
    check=True,
)
subprocess.run(
    [
        "python",
        base_path / "03_update_pyproject.py",
        str(Path("~/repos/weave-stainless").expanduser()),
        "weave-trace",
    ],
    check=True,
)
