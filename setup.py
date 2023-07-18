import os
from pathlib import Path
from setuptools import setup  # type: ignore[import]
from setuptools.command.build import build  # type: ignore[import]
from setuptools.command.editable_wheel import editable_wheel  # type: ignore[import]
from setuptools.command.sdist import sdist  # type: ignore[import]
import subprocess
import tarfile
import tempfile
from typing import Union
import urllib.request
from urllib.error import HTTPError

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
        build_script = str(Path("weave", "frontend", "build.sh"))
        subprocess.run(["bash", build_script], cwd=ROOT)
    except OSError:
        raise RuntimeError("Failed to build frontend.")


def download_and_extract_tarball(
    url: str, extract_path: Union[Path, str] = "."
) -> None:
    file_name = os.path.basename(url)
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = os.path.join(temp_dir, file_name)
        try:
            # Download the tarball
            urllib.request.urlretrieve(url, temp_path)
        except urllib.error.URLError as e:
            raise RuntimeError(f"Couldn't download the tarball {url} due to error: {e}")

        try:
            # Extract the tarball
            if tarfile.is_tarfile(temp_path):
                with tarfile.open(temp_path, "r:gz") as tar:
                    tar.extractall(path=extract_path)
                # TODO: detect when the extracted assets are out of sync with git
            else:
                raise RuntimeError(f"{file_name} is not a tarball file.")
        except tarfile.TarError as e:
            raise RuntimeError(f"Couldn't extract {file_name} due to error: {e}")


def download_frontend() -> None:
    sha = open(ROOT / "weave" / "frontend" / "sha1.txt").read().strip()
    url = f"https://storage.googleapis.com/wandb-cdn-prod/weave/{sha}.tar.gz"
    try:
        download_and_extract_tarball(url, extract_path=ROOT / "weave")
    except HTTPError:
        print(f"Warning: Failed to download frontend for sha {sha}")


class Build(build):  # type: ignore
    def run(self) -> None:
        if FORCE_BUILD:
            build_frontend()
        elif not IS_BUILT:
            download_frontend()
        super().run()


class EditableWheel(editable_wheel):  # type: ignore
    def run(self) -> None:
        if FORCE_BUILD:
            build_frontend()
        elif not IS_BUILT:
            download_frontend()
        super().run()


class Sdist(sdist):  # type: ignore
    def run(self) -> None:
        if FORCE_BUILD:
            build_frontend()
        elif not IS_BUILT:
            download_frontend()
        super().run()


setup(cmdclass={"build": Build, "editable_wheel": EditableWheel, "sdist": Sdist})
