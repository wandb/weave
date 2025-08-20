# Weave Release Process

This document outlines how to publish a new Weave release to our public [PyPI package](https://pypi.org/project/weave/).

1. Verify the head of master is ready for release and announce merge freeze to the Weave team while the release is being published (Either ask an admin on the Weave repo to place a freeze on https://www.mergefreeze.com/ or use the mergefreeze Slack app if it is set up or just post in Slack)

2. Manual Verifications:
   - Run `make prerelease-dry-run` to verify that the dry run script works.
   - You should also run through this [sample notebook](https://colab.research.google.com/drive/1DmkLzhFCFC0OoN-ggBDoG1nejGw2jQZy#scrollTo=29hJrcJQA7jZ) remember to install from master. You can also just run the [quickstart](http://wandb.me/weave_colab).

3. To prepare a PATCH release, go to GitHub Actions and run the [bump-python-sdk-version](https://github.com/wandb/weave/actions/workflows/bump_version.yaml) workflow on master. This will:

   - Create a new patch version by dropping the pre-release (e.g., `x.y.z-dev0` -> `x.y.z`) and tag this commit with `x.y.z`
   - Create a new dev version by incrementing the dev version (e.g., `x.y.z` -> `x.y.(z+1)-dev0`) and commit this to master
   - Both of these commits will be pushed to master
   - Note: if you need to make a new minor or major release, you can do these steps manually with 2 PRs modifying the files in `weave/version.py` and `weave/pyproject.toml`

4. Go to the [publish-pypi-release](https://github.com/wandb/weave/actions/workflows/release.yaml) GitHub action and trigger a new release from the `x.y.z` tag (NOT MASTER). For riskier releases, make sure `Use Test PyPI` is checked so we first publish a test package to [test.pypi.org](https://test.pypi.org/project/weave/#history).

5. Verify the new version of Weave exists in [PyPI](https://pypi.org/project/weave/) once it is complete.

6. Go to the [GitHub new release page](https://github.com/wandb/weave/releases/new). Select the new tag, and click "Generate release notes". Publish the release.

7. Finally, announce that the merge freeze is over.
