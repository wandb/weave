"""Contains the version of the Weave SDK.

This version is used by pyproject.toml to specify the version of the Weave SDK and
imported by the library for runtime access. It must be kept in sync with pyproject.toml,
specifically the [tool.bumpversion] section:

```
[tool.bumpversion]
current_version = "M.m.p-dev0"
```

We use Semantic Versioning (https://semver.org/). The version number is in the format
MAJOR.MINOR.PATCH[-PRERELEASE].

- MAJOR version when you make incompatible API changes,
- MINOR version when you add functionality in a backwards compatible manner, and
- PATCH version when you make backwards compatible bug fixes.

For the most part, we are incrementing PATCH until we complete the core functionality.

As specified by Semantic Versioning, the PRERELEASE version is optional and can be
appended to the PATCH version. Specifically:

```
When major, minor, and patch are equal, a pre-release version has lower precedence than a normal version:

Example: 1.0.0-alpha < 1.0.0.
```

The intention is to have a PRERELEASE version of the form of `dev0` for nearly every commit
on the main branch. However, the released commit will not have a PRERELEASE version. For example:

* Development happens on X.Y.Z-dev0
* Release commit bumps the version to >=X.Y.Z, noted X'.Y'.Z', tagging such commit
* Development continues on (>X.Y.Z)-dev0.
    * Note: if X' == X, Y' == Y, and Z' == Z, then the version is bumped to X'.Y'.(Z'+1)-dev0. Else, the version is bumped to X'.Y'.Z'-dev0.


This is all facilitated using `make bumpversion` which is a wrapper around `bump-my-version`.

Please see the `bump-my-version` documentation for more information:
https://github.com/callowayproject/bump-my-version. Additional configuration can be found in
`pyproject.toml`.

"""

VERSION = "0.51.45"
