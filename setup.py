from setuptools import setup

with open("requirements.txt") as requirements_file:
    requirements = requirements_file.read().splitlines()


setup(
    name="weave",
    version="0.0.1.dev1",
    description="Weave internal development package.",
    author="Weights & Biases",
    author_email="support@wandb.com",
    url="https://github.com/wandb/end-to-end",
    packages=[
        "weave",
        "weave.ops_primitives",
        "weave.ops_domain",
        "weave.panels",
        "weave.ecosystem",
    ],
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
