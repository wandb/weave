"""Standard version conventions."""

from bumpversion.versioning.models import VersionComponentSpec, VersionSpec

# Adapted from https://packaging.python.org/en/latest/specifications/version-specifiers/
PEP440_PATTERN = r"""
    v?
    (?:
        (?P<major>0|[1-9]\d*)\.
        (?P<minor>0|[1-9]\d*)\.
        (?P<patch>0|[1-9]\d*)
        (?:                                          # pre-release
            [-_\.]?
            (?P<pre>
                (?P<pre_l>a|b|c|rc|alpha|beta|pre|preview)
                [-_\.]?
                (?P<pre_n>[0-9]+)?
            )
        )?
        (?:                                          # post release
            [-_\.]?
            (?P<post>
                post
                [-_\.]?
                [0-9]+
            )
        )?
        (?:                                          # dev release
            [-_\.]?
            (?P<dev>
                dev
                [-_\.]?
                [0-9]+
            )
        )?
    )
    (?:\+(?P<local>[a-z0-9]+(?:[-_\.][a-z0-9]+)*))?   # local version
"""
PEP440_SERIALIZE_PATTERNS = [
    "{major}.{minor}.{patch}{pre_l}{pre_n}.{post}.{dev}+{local}",
    "{major}.{minor}.{patch}{pre_l}{pre_n}.{post}.{dev}",
    "{major}.{minor}.{patch}{pre_l}{pre_n}.{post}+{local}",
    "{major}.{minor}.{patch}{pre_l}{pre_n}.{dev}+{local}",
    "{major}.{minor}.{patch}.{post}.{dev}+{local}",
    "{major}.{minor}.{patch}{pre_l}{pre_n}.{post}",
    "{major}.{minor}.{patch}{pre_l}{pre_n}.{dev}",
    "{major}.{minor}.{patch}{pre_l}{pre_n}+{local}",
    "{major}.{minor}.{patch}.{post}.{dev}",
    "{major}.{minor}.{patch}.{post}+{local}",
    "{major}.{minor}.{patch}.{dev}+{local}",
    "{major}.{minor}.{patch}.{pre_l}{pre_n}",
    "{major}.{minor}.{patch}.{post}",
    "{major}.{minor}.{patch}.{dev}",
    "{major}.{minor}.{patch}+{local}",
    "{major}.{minor}.{patch}",
]
PEP440_COMPONENT_CONFIGS = {
    "major": VersionComponentSpec(),
    "minor": VersionComponentSpec(),
    "patch": VersionComponentSpec(),
    "pre_l": VersionComponentSpec(values=["", "a", "b", "rc"]),
    "pre_n": VersionComponentSpec(),
    "post": VersionComponentSpec(depends_on="patch"),
    "dev": VersionComponentSpec(depends_on="patch"),
    "local": VersionComponentSpec(depends_on="patch", optional_value=""),
}


def pep440_version_spec() -> VersionSpec:
    """Return a VersionSpec for PEP 440."""
    return VersionSpec(components=PEP440_COMPONENT_CONFIGS)


# Adapted from https://regex101.com/r/Ly7O1x/3/
SEMVER_PATTERN = r"""
    (?P<major>0|[1-9]\d*)\.
    (?P<minor>0|[1-9]\d*)\.
    (?P<patch>0|[1-9]\d*)
    (?:
        -                             # dash separator for pre-release section
        (?P<pre_l>[a-zA-Z-]+)         # pre-release label
        (?P<pre_n>0|[1-9]\d*)         # pre-release version number
    )?                                # pre-release section is optional
    (?:
        \+                            # plus separator for build metadata section
        (?P<buildmetadata>
            [0-9a-zA-Z-]+
            (?:\.[0-9a-zA-Z-]+)*
        )
    )?                                # build metadata section is optional
"""
SEMVER_SERIALIZE_PATTERNS = [
    "{major}.{minor}.{patch}-{pre_l}{pre_n}+{buildmetadata}",
    "{major}.{minor}.{patch}-{pre_l}{pre_n}",
    "{major}.{minor}.{patch}+{buildmetadata}",
    "{major}.{minor}.{patch}",
]
SEMVER_COMPONENT_CONFIGS = {
    "major": VersionComponentSpec(),
    "minor": VersionComponentSpec(),
    "patch": VersionComponentSpec(),
    "pre_l": VersionComponentSpec(values=["", "a", "b", "rc"]),
    "pre_n": VersionComponentSpec(),
    "buildmetadata": VersionComponentSpec(independent=True),
}


def semver_spec() -> VersionSpec:
    """Return a VersionSpec for SEMVER."""
    return VersionSpec(components=SEMVER_COMPONENT_CONFIGS)
