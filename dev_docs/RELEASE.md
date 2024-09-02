# Weave Release Process

This document outlines how to publish a new weave release to our public [pypi package](https://pypi.org/project/weave/).

1. To prepare a release, update the version number in `weave/version.py` to the next minor version. E.g. `0.27.0 -> 0.28.0`

2. Create a new PR with title `chore(dev): publish weave release 0.x.0` replacing `x` with the new version number

3. Once the PR passes all checks, verify the head of master is ready for release and annouce merge freeze to weave team while the release is being published (Either ask an admin on the weave repo to place a freeze on https://www.mergefreeze.com/ or use the mergefreeze slack app if it is set up)

4. Merge the PR in step (2), verify the frontend assets are up to date by checking all runs of the [upload-frontend-assets](https://github.com/wandb/weave/actions/workflows/upload-assets.yaml) action have completed

5. Go to the [publish-pypi-release](https://github.com/wandb/weave/actions/workflows/release.yaml) Github action and trigger a new build from the master branch, make sure `Use Test Pypi` is checked so we first publish a test package.

6. Verify the new version of weave exist in [test pypi](https://test.pypi.org/project/weave/). You should also run through this [sample notebook](https://colab.research.google.com/drive/1DmkLzhFCFC0OoN-ggBDoG1nejGw2jQZy#scrollTo=29hJrcJQA7jZ) (remember to update the version number to the new version you just published) to double check the new package is correct.

7. Once you are confident the test pypi package is valid. Run the same [publish-pypi-release](https://github.com/wandb/weave/actions/workflows/release.yaml) action without the `Use Test Pypi` flag with branch set as `master`. This should generate a new package in [pypi](https://pypi.org/project/weave/) once it is complete.

8. Tag the commit of the release and push the tag to Github using the following commands:
```
git tag -a v0.<x>.0 <sha of the release commit> -m "useful message about the new features in this release"
git push origin v0.<x>.0
```

9. Finally, deploy weave python
