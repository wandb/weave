from setuptools import setup
import pkg_resources


def convert_git_requirement(req):
    # If requirements contains a git repo like
    # git+https://github.com/wandb/client.git@dtypes/safer_image_restore#egg=wandb
    # convert it to "wandb @ git+https://github.com/wandb/client.git@dtypes/safer_image_restore#egg=wandb""
    if "egg=" in req:
        _, package_name = req.split("egg=", 1)
        return f"{package_name} @ {req}"
    return req


with open("requirements.txt") as requirements_file:
    requirements = [
        convert_git_requirement(str(requirement))
        for requirement in pkg_resources.parse_requirements(requirements_file)
    ]

with open("requirements.ecosystem.txt") as requirements_file:
    requirements_ecosystem = [
        convert_git_requirement(str(requirement))
        for requirement in pkg_resources.parse_requirements(requirements_file)
    ]

setup(
    name="weave",
    version="0.0.3.dev1",
    description="Weave internal development package.",
    author="Weights & Biases",
    author_email="support@wandb.com",
    url="https://github.com/wandb/end-to-end",
    package_dir={"weave": "weave"},
    include_package_data=True,
    package_data={"weave": ["frontend/**"]},
    install_requires=requirements,
    license="MIT license",
    zip_safe=False,
    python_requires=">=3.6",
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
    extras_require={"ecosystem": requirements_ecosystem},
)
