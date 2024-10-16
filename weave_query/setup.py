from setuptools import find_namespace_packages, setup  # type: ignore[import]
from setuptools.command.build import build  # type: ignore[import]
from setuptools.command.editable_wheel import editable_wheel  # type: ignore[import]
from setuptools.command.sdist import sdist  # type: ignore[import]






class Build(build):  # type: ignore
    def run(self) -> None:
        super().run()


class EditableWheel(editable_wheel):  # type: ignore
    def run(self) -> None:
        super().run()


class Sdist(sdist):  # type: ignore
    def run(self) -> None:
        super().run()


setup(
    cmdclass={"build": Build, "editable_wheel": EditableWheel, "sdist": Sdist},
    packages=find_namespace_packages(include=["weave*"]),
)
