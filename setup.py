from setuptools import setup


def convert_git_requirement(req):
    # If requirements contains a git repo like
    # git+https://github.com/wandb/client.git@dtypes/safer_image_restore#egg=wandb
    # convert it to "wandb @ git+https://github.com/wandb/client.git@dtypes/safer_image_restore#egg=wandb""
    if "egg=" in req:
        _, package_name = req.split("egg=", 1)
        return f"{package_name} @ {req}"
    return req


with open("requirements.txt") as requirements_file:
    requirements = requirements_file.read().splitlines()
requirements = [convert_git_requirement(req) for req in requirements]


setup(
    name="weave",
    version="0.0.1.dev1",
    description="Weave internal development package.",
    author="Weights & Biases",
    author_email="support@wandb.com",
    url="https://github.com/wandb/end-to-end",
    package_dir={"weave": "weave"},
    include_package_data=True,
    install_requires=requirements,
    license="MIT license",
    zip_safe=False,
    python_requires=">=3.6",
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
)
