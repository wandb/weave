import os
from pathlib import Path
from setuptools import setup  # type: ignore[import]
from setuptools.command.build import build  # type: ignore[import]
from setuptools.command.editable_wheel import editable_wheel  # type: ignore[import]
from setuptools.command.sdist import sdist  # type: ignore[import]
import subprocess

ROOT = Path(__file__).resolve().parent
SKIP_BUILD = os.environ.get("WEAVE_SKIP_BUILD", False)
IS_BUILT = (ROOT / "weave" / "frontend" / "assets").is_dir() or SKIP_BUILD
FORCE_BUILD = os.environ.get("WEAVE_FORCE_BUILD", False)


def check_build_deps() -> bool:
    have_yarn = False
    try:
        subprocess.run(["yarn", "--version"], capture_output=True)
        have_yarn = True
    except OSError:
        pass

    if not have_yarn:
        try:
            print("Attempting to install yarn...")
            subprocess.run(["npm", "install", "-g", "yarn"], capture_output=True)
        except OSError:
            raise RuntimeError(
                "You must have node v16+ (https://nodejs.org/en/download) installed to build weave."
            )
    return True


def build_frontend() -> None:
    check_build_deps()
    try:
        subprocess.run(["bash", "./weave/frontend/build.sh"], cwd=ROOT)
    except OSError:
        raise RuntimeError("Failed to build frontend.")


class Build(build):  # type: ignore
    def run(self) -> None:
        if not IS_BUILT or FORCE_BUILD:
            build_frontend()
        super().run()


class EditableWheel(editable_wheel):  # type: ignore
    def run(self) -> None:
        if not IS_BUILT or FORCE_BUILD:
            build_frontend()
        super().run()


class Sdist(sdist):  # type: ignore
    def run(self) -> None:
        if not IS_BUILT or FORCE_BUILD:
            build_frontend()
        super().run()


setup(cmdclass={"build": Build, "editable_wheel": EditableWheel, "sdist": Sdist})
