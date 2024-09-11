# Weave Release Process

This document outlines how to publish a new weave release to our public [pypi package](https://pypi.org/project/weave/).

1. Verify the head of master is ready for release and annouce merge freeze to weave team while the release is being published (Either ask an admin on the weave repo to place a freeze on https://www.mergefreeze.com/ or use the mergefreeze slack app if it is set up or just post in slack)

2. You should also run through this [sample notebook](https://colab.research.google.com/drive/1DmkLzhFCFC0OoN-ggBDoG1nejGw2jQZy#scrollTo=29hJrcJQA7jZ) remember to install from master. You can also just run the [quickstart](http://wandb.me/weave_colab).

3. To prepare a PATCH release, got to GitHub actions and run the `bump-python-sdk-version` workflow on master. This will:
   - Create a new patch version by dropping the pre-release (eg. `x.y.z-dev0` -> `x.y.z`) and tag this commit with `x.y.z`
   - Create a new dev version by incrementing the dev version (eg. `x.y.z` -> `x.y.(z+1)-dev0`) and commit this to master
   - Both of these commits will be pushed to master
   - Note: if you need to make a new minor or major release, you can do these steps manually with 2 PRs modifying the files in `weave/version.py` and `weave/pyproject.toml`

4. Go to the [publish-pypi-release](https://github.com/wandb/weave/actions/workflows/release.yaml) Github action and trigger a new release from the `x.y.z` branch (NOT MASTER), For riskier releases make sure `Use Test Pypi` is checked so we first publish a test package.

5. Verify the new version of weave exist in [pypi](https://pypi.org/project/weave/) once it is complete.

6. Go to github, and click the release tag and click `Draft a New Release`. Select the new tag, and click generate release notes. Publish the release.

7. Finally, announce that merge freeze is over
